from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
import requests
import os
import tempfile
from datetime import datetime

from agents.intentAgent import create_intent_agent
from agents.ragAgent import create_ragging_agent
from faster_whisper import WhisperModel
from user_context import UserDataContext

# === Environment setup ===
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

if not MONGO_URI or not SLACK_BOT_TOKEN:
    raise RuntimeError("Missing MONGO_URI or SLACK_BOT_TOKEN")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["fransa_demo"]
users_col = db["users"]
cards_col = db["cards"]
transactions_col = db["transactions"]

# === Whisper STT ===
stt_model = WhisperModel("small", device="cpu", compute_type="int8")
AUDIO_FILETYPES = {"mp3", "m4a", "wav", "ogg", "webm", "mp4"}

# === Helper functions ===
def is_audio_file(file_obj: Dict) -> bool:
    mimetype = (file_obj.get("mimetype") or "").lower()
    filetype = (file_obj.get("filetype") or "").lower()
    return mimetype.startswith("audio/") or filetype in AUDIO_FILETYPES


def download_slack_file(file_obj: Dict) -> str:
    url = file_obj.get("url_private_download") or file_obj.get("url_private")
    if not url:
        raise ValueError("Slack file has no downloadable URL")
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    suffix = "." + (file_obj.get("filetype") or "bin")
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(resp.content)
    return tmp_path


def transcribe_audio_file(path: str) -> str:
    print(f"[DEBUG] Transcribing audio file at {path}")
    segments, _ = stt_model.transcribe(path, beam_size=5)
    transcript = " ".join([s.text for s in segments]).strip()
    print(f"[DEBUG] Transcription result: {transcript[:100]}...")
    return transcript or "[unintelligible voice message]"


def send_message_to_slack(channel: str, text: str):
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"channel": channel, "text": text}
    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)


# === FastAPI app ===
app = FastAPI(title="Banking Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_sessions: Dict[str, List[Dict[str, str]]] = {}

# === Data models ===
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    clientId: Optional[str] = None
    authToken: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    session_id: str
    conversation_history: List[Dict[str, str]]


class SessionResponse(BaseModel):
    session_id: str
    conversation_history: List[Dict[str, str]]


# === Slack endpoint ===
@app.post("/slack/events")
async def slack_events(request: Request):
    # Handle Slack verification & retries
    if request.headers.get("X-Slack-Retry-Num"):
        return {"ok": True}

    data = await request.json()
    if data.get("type") == "url_verification":
        return {"challenge": data["challenge"]}
    if data.get("type") != "event_callback":
        return {"ok": True}

    event = data.get("event", {})
    if not event.get("user") or event.get("subtype") == "bot_message":
        return {"ok": True}

    user_id = event["user"]
    channel = event["channel"]
    text = (event.get("text") or "").strip()
    print(f"[DEBUG] Incoming message from Slack user {user_id}: {text}")

    # Handle Slack voice/audio attachments
    files = event.get("files", [])
    if files:
        for f in files:
            if is_audio_file(f):
                print(f"[DEBUG] Detected audio file from Slack user {user_id}")
                try:
                    path = download_slack_file(f)
                    text = transcribe_audio_file(path)
                    os.remove(path)
                    print(f"[DEBUG] Transcribed audio: {text}")
                except Exception as e:
                    print(f"[ERROR] Audio processing failed: {e}")
                    send_message_to_slack(channel, f"⚠️ Could not process voice message: {str(e)}")
                    return {"ok": True}
                break

    if not text:
        print(f"[DEBUG] No text or audio content from {user_id}, ignoring.")
        return {"ok": True}

    # Authenticate user
    user_doc = users_col.find_one({"slack_id": user_id})
    if not user_doc:
        print(f"[DEBUG] Ignored unregistered Slack user {user_id} in channel {channel}")
        return {"ok": True}

    client_id = user_doc.get("clientId")
    if not client_id:
        send_message_to_slack(channel, "⚠️ No client ID found for this account.")
        return {"ok": True}

    # Create user context
    user_ctx = UserDataContext(client_id, cards_col, transactions_col)

    # Session prep
    session_id = f"slack_{user_id}"
    chat_sessions.setdefault(session_id, [])
    conversation_history = chat_sessions[session_id]

    # Process message
    try:
        intent_agent = create_intent_agent(user_ctx)
        result = intent_agent.invoke({
            "user_input": text,
            "conversation_history": conversation_history,
        })
        intent = result.get("intent", "unknown")
        print(f"[DEBUG] Detected intent: {intent}")

        if intent == "general_query":
            print("[DEBUG] Routing to RAG agent...")
            rag_agent = create_ragging_agent(bank_name="Bank_of_Beirut")
            rag_result = rag_agent.invoke({
                "user_input": text,
                "intent": "general_query",
                "bank_name": "fransa_demo",
                "conversation_history": conversation_history,
            })
            response_text = rag_result["result"]["content"]
        else:
            response_text = result.get("result", {}).get("content", "No response")

        chat_sessions[session_id] = result.get("conversation_history", [])

    except Exception as e:
        print(f"[ERROR] Slack processing failed: {e}")
        send_message_to_slack(channel, f"⚠️ Error: {str(e)}")
        return {"ok": False}

    send_message_to_slack(channel, response_text)
    return {"ok": True}


# === Web chat endpoint ===
@app.post("/chat", response_model=ChatResponse)
async def chat(chat_message: ChatMessage):
    try:
        if not chat_message.clientId:
            raise HTTPException(status_code=401, detail="Missing clientId")

        user_ctx = UserDataContext(chat_message.clientId, cards_col, transactions_col)
        session_id = chat_message.session_id or f"session_{datetime.now().timestamp()}"
        chat_sessions.setdefault(session_id, [])
        conversation_history = chat_sessions[session_id]

        intent_agent = create_intent_agent(user_ctx)
        result = intent_agent.invoke({
            "user_input": chat_message.message,
            "conversation_history": conversation_history,
        })

        intent = result.get("intent", "unknown")
        print(f"[DEBUG] Detected intent: {intent}")

        if intent == "general_query":
            rag_agent = create_ragging_agent(bank_name="fransa_demo")
            rag_result = rag_agent.invoke({
                "user_input": chat_message.message,
                "intent": "general_query",
                "bank_name": "fransa_demo",
                "conversation_history": conversation_history,
            })
            response_text = rag_result["result"]["content"]
        else:
            response_text = result["result"]["content"]

        chat_sessions[session_id] = result.get("conversation_history", [])

        return ChatResponse(
            response=response_text,
            intent=intent,
            session_id=session_id,
            conversation_history=result["conversation_history"],
        )

    except Exception as e:
        print(f"[ERROR] /chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/new", response_model=SessionResponse)
async def new_chat_session():
    session_id = f"session_{datetime.now().timestamp()}"
    chat_sessions[session_id] = []
    return SessionResponse(session_id=session_id, conversation_history=[])


@app.get("/chat/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(session_id=session_id, conversation_history=chat_sessions[session_id])


@app.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    chat_sessions[session_id] = []
    return {"message": "Session cleared successfully", "session_id": session_id}


@app.get("/chat/sessions")
async def list_sessions():
    return {"sessions": [{"session_id": sid, "message_count": len(hist)} for sid, hist in chat_sessions.items()]}


@app.get("/")
async def root():
    return {"message": "Welcome to the Banking Assistant API!", "status": "running", "version": "2.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
