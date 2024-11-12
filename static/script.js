document.getElementById("text-button").addEventListener("click", function() {
    document.getElementById("text-input-div").style.display = "block";
    document.getElementById("voice-input-div").style.display = "none";
});

document.getElementById("voice-button").addEventListener("click", function() {
    document.getElementById("text-input-div").style.display = "none";
    document.getElementById("voice-input-div").style.display = "block";
    startVoiceRecording();
});

let mediaRecorder;
let audioChunks = [];
let mediaStream;

function startVoiceRecording() {
    audioChunks = [];
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaStream = stream;  // 스트림 객체를 저장합니다.
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();

            mediaRecorder.addEventListener("dataavailable", event => {
                audioChunks.push(event.data);
            });

            document.getElementById("voice-input-div").style.display = "block";
            document.getElementById("text-input-div").style.display = "none";
        })
        .catch(error => console.error('Error accessing microphone:', error));
}

function stopVoiceRecording() {
    mediaRecorder.stop();
    mediaRecorder.addEventListener("stop", () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append("audio", audioBlob);

        fetch("/process_voice", {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log('Voice Input Response:', data);  // 로그 추가
            if (data.error) {
                console.error('Error from server:', data.error);
                return;
            }
            displayMessage(data.convertedText, 'user-message');
            displayMessage(data.modelOutput, 'model-response');
            playAudio(data.audioBlob);
        })
        .catch(error => console.error('Error:', error));

        // 스트림을 중지하여 마이크 동작 아이콘을 비활성화합니다.
        mediaStream.getTracks().forEach(track => track.stop());
    });

    document.getElementById("voice-input-div").style.display = "none";
}

function sendTextInput() {
    const userInput = document.getElementById("user-text-input").value;
    fetch("/process_text", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ user_message: userInput })
    })
    .then(response => response.json())
    .then(data => {
        displayMessage(userInput, 'user-message');
        displayMessage(data.modelOutput, 'model-response');
        playAudio(data.audioBlob);
    })
    .catch(error => console.error('Error:', error));
}

function displayMessage(message, className) {
    const chatContainer = document.getElementById("chat-container");
    const messageBubble = document.createElement("div");
    messageBubble.className = `chat-bubble ${className}`;
    messageBubble.innerText = message;
    chatContainer.appendChild(messageBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function playAudio(audioData) {
    const audioUrl = `data:audio/mp3;base64,${audioData}`;
    const audio = new Audio(audioUrl);
    audio.play();
}
