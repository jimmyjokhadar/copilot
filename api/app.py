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
from faster_whisper import WhisperModel
from user_context import UserDataContext

load_dotenv()

# === Environment setup ===
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
async def is_audio_file(file_obj: Dict) -> bool:
    mimetype = (file_obj.get("mimetype") or "").lower()
    filetype = (file_obj.get("filetype") or "").lower()
    return mimetype.startswith("audio/") or filetype in AUDIO_FILETYPES


async def download_slack_file(file_obj: Dict) -> str:
    """Download Slack file temporarily (requires files:read)."""
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


async def transcribe_audio_file(path: str) -> str:
    """Run faster-whisper on file."""
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

    # Fetch user doc
    user_doc = users_col.find_one({"slack_id": user_id})
    if not user_doc:
        send_message_to_slack(channel, "❌ Unregistered user. Please register your Slack account.")
        return {"ok": False}

    client_id = user_doc.get("clientId")
    if not client_id:
        send_message_to_slack(channel, "⚠️ No client ID found for this account.")
        return {"ok": False}

    # === Create user context ===
    user_ctx = UserDataContext(client_id, cards_col, transactions_col)

    # === Prepare session ===
    session_id = f"slack_{user_id}"
    chat_sessions.setdefault(session_id, [])
    conversation_history = chat_sessions[session_id]

    # === Create user-scoped agent ===
    intent_agent = create_intent_agent(user_ctx)

    # === Process message ===
    try:
        result = intent_agent.invoke({
            "user_input": text,
            "conversation_history": conversation_history,
        })
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

        # Build user context
        user_ctx = UserDataContext(chat_message.clientId, cards_col, transactions_col)
        session_id = chat_message.session_id or f"session_{datetime.now().timestamp()}"
        chat_sessions.setdefault(session_id, [])
        conversation_history = chat_sessions[session_id]

        intent_agent = create_intent_agent(user_ctx)
        result = intent_agent.invoke({
            "user_input": chat_message.message,
            "conversation_history": conversation_history,
        })

        chat_sessions[session_id] = result.get("conversation_history", [])
        return ChatResponse(
            response=result["result"]["content"],
            intent=result["intent"],
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
