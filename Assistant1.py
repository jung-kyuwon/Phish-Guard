import os
import json
import time
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv  # .env 파일을 불러오기 위해 추가

# .env 파일 로드
load_dotenv()

# API Key와 Assistant ID 환경 변수에서 가져오기
api_key = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

if api_key is None:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

def show_json(obj):
    # obj의 속성을 JSON 형태로 변환한 후 출력합니다.
    serializable_obj = {k: v for k, v in obj.__dict__.items() if isinstance(v, (str, int, float, bool, list, dict))}
    print(json.dumps(serializable_obj, indent=2))

# OpenAI 객체 생성
try:
    client = OpenAI(api_key=api_key)
except OpenAIError as e:
    print(f"Failed to initialize OpenAI client: {e}")
    exit(1)

def create_new_thread():
    # 새로운 스레드를 생성합니다.
    thread = client.beta.threads.create()
    return thread

thread = create_new_thread()
# 새로운 스레드를 생성합니다.
show_json(thread)
# 새롭게 생성한 스레드 ID를 저장합니다.
THREAD_ID = thread.id

def wait_on_run(run, thread_id):
    while run.status == "queued" or run.status == "in_progress":
        # 3-3. 실행 상태를 최신 정보로 업데이트합니다.
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run

def submit_message(assistant_id, thread_id, user_message):
    # 3-1. 스레드에 종속된 메시지를 '추가' 합니다.
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="asc")
    if len(messages.data) == 0:
        prompt = f"\"{user_message}\"에 대해서 조언을 해줘. 어떤 유형의 사기인지 식별하고 간단한 조언을 2가지 이내로 해줘. 그리고 종료해줘."
    else:
        prompt = user_message

    client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=prompt
    )
    # 3-2. 스레드를 실행합니다.
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    return run

def get_response(thread_id):
    # 3-4. 스레드에 종속된 메시지를 '조회' 합니다.
    response = client.beta.threads.messages.list(thread_id=thread_id, order="asc")
    return response.data

def print_message(response):
    for res in response:
        print(f"[{res.role.upper()}]\n{res.content[0].text.value}\n")

def ask(assistant_id, thread_id, user_message):
    run = submit_message(
        assistant_id,
        thread_id,
        user_message,
    )
    # 실행이 완료될 때까지 대기합니다.
    run = wait_on_run(run, thread_id)
    print_message(get_response(thread_id)[-2:])
    return run

def summarize_conversation(assistant_id, thread_id):
    messages = get_response(thread_id)
    conversation_text = "\n".join([f"{msg.role}: {msg.content[0].text.value}" for msg in messages])

    summary_request = f"Summarize the following conversation:\n\n{conversation_text}"

    run = submit_message(
        assistant_id,
        thread_id,
        summary_request,
    )
    # 실행이 완료될 때까지 대기합니다.
    run = wait_on_run(run, thread_id)
    print_message(get_response(thread_id)[-2:])
    return run

def handle_specific_question(assistant_id, thread_id, user_message):
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="asc")
    if len(messages.data) == 0:
        prompt = f"\"{user_message}\"에 대해서 보이스피싱 판별을 해줘. 어떤 유형 보이스피싱 사기인지 식별하고 간단한 조언을 1가지로 해줘. 그리고 종료해줘."
    else:
        prompt = user_message

    run = submit_message(
        assistant_id,
        thread_id,
        prompt,
    )
    # 실행이 완료될 때까지 대기합니다.
    run = wait_on_run(run, thread_id)
    response = get_response(thread_id)[-1]
    response_text = response.content[0].text.value

    # 질문 제출 및 답변 출력
    print(f"질문 : {user_message}")
    print(f"답변 : {response_text}")

# 예시 질문과 답변
questions = [
    "녹취 중에는 잡음이나 제3자 목소리가 개입되면 안되고 지금 수사중인 사건이라서 수사 종료되기 전까지 제3자에게 사건 내용에 대해서 발설하시면 안 되십니다."
]

for question in questions:
    handle_specific_question(ASSISTANT_ID, THREAD_ID, question)