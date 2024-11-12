from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google.cloud import texttospeech
from google.cloud import speech_v1p1beta1 as speech
from openai import OpenAI, OpenAIError
import os
import time
import wave
from gtts import gTTS
import subprocess
import base64
from dotenv import load_dotenv  # .env 파일에서 환경 변수를 로드하기 위해 사용합니다.

# .env 파일을 로드합니다.
load_dotenv()

app = Flask(__name__)
CORS(app)

# 환경 변수에서 JSON 파일 경로 및 API 키를 로드합니다.
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH")
api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_wY66De4O9X50ZiwXpqT0nhua")  # 기본 ID 설정

if api_key is None:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=api_key)

def create_new_thread():
    thread = client.beta.threads.create()
    return thread.id

THREAD_ID = create_new_thread()

def submit_message(assistant_id, thread_id, user_message):
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="asc")
    if len(messages.data) == 0:
        prompt = f"\"{user_message}\"에 대해서 보이스피싱 판별을 해줘. 어떤 유형 보이스피싱 사기인지 식별하고 간단한 조언을 1가지로 해줘. 그리고 종료해줘."
    else:
        prompt = user_message

    client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=prompt
    )
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    return run

def wait_on_run(run, thread_id):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run

def get_response(thread_id):
    response = client.beta.threads.messages.list(thread_id=thread_id, order="asc")
    return response.data

def text_to_speech(text, lang="ko"):
    tts = gTTS(text=text, lang=lang)
    filename = "response.mp3"
    tts.save(filename)
    return filename

def get_sample_rate(wav_path):
    with wave.open(wav_path, 'rb') as wav_file:
        return wav_file.getframerate()

def transcribe_audio(wav_path):
    client = speech.SpeechClient()
    sample_rate_hertz = get_sample_rate(wav_path)
    
    with open(wav_path, 'rb') as audio_file:
        content = audio_file.read()
    
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate_hertz,
        language_code='ko-KR'
    )
    
    response = client.recognize(config=config, audio=audio)
    
    for result in response.results:
        print('Transcript: {}'.format(result.alternatives[0].transcript))
        return result.alternatives[0].transcript

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_text', methods=['POST'])
def process_text():
    user_message = request.json['user_message']
    run = submit_message(ASSISTANT_ID, THREAD_ID, user_message)
    run = wait_on_run(run, THREAD_ID)
    response = get_response(THREAD_ID)[-1]
    response_text = response.content[0].text.value
    tts_filename = text_to_speech(response_text)
    
    with open(tts_filename, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode('utf-8')
    
    return jsonify({'modelOutput': response_text, 'audioBlob': audio_data})

@app.route('/process_voice', methods=['POST'])
def process_voice():
    audio_file = request.files["audio"]
    audio_path = "audio.webm"
    wav_path = "audio.wav"

    with open(audio_path, "wb") as f:
        f.write(audio_file.read())
    print(f"Audio file saved at {audio_path}")

    try:
        # 기존 wav 파일 삭제 (있을 경우)
        if os.path.exists(wav_path):
            os.remove(wav_path)
            print(f"Existing {wav_path} deleted")

        # FFmpeg 명령을 사용하여 webm 파일을 wav 파일로 변환
        command = f"ffmpeg -i {audio_path} {wav_path}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(f"FFmpeg output: {result.stdout}")
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return jsonify({'error': 'Audio conversion failed'}), 500

        print(f"Audio file converted to {wav_path}")
    except Exception as e:
        print(f"Error converting audio file: {e}")
        return jsonify({'error': 'Audio conversion failed'}), 500

    # 변환된 파일이 존재하는지 확인
    if not os.path.exists(wav_path):
        print("Converted wav file does not exist")
        return jsonify({'error': 'Converted wav file does not exist'}), 500

    try:
        user_message = transcribe_audio(wav_path)
        print(f"Recognized text: {user_message}")
    except Exception as e:
        error_msg = f"Error recognizing speech: {e}"
        print(error_msg)
        return jsonify({'error': error_msg}), 500

    run = submit_message(ASSISTANT_ID, THREAD_ID, user_message)
    run = wait_on_run(run, THREAD_ID)
    response = get_response(THREAD_ID)[-1]
    response_text = response.content[0].text.value
    
    tts_filename = text_to_speech(response_text)
    
    with open(tts_filename, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode('utf-8')
    
    return jsonify({'convertedText': user_message, 'modelOutput': response_text, 'audioBlob': audio_data})

if __name__ == "__main__":
    app.run(debug=True)