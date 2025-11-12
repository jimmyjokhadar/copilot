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

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

if not MONGO_URI or not SLACK_BOT_TOKEN:
    raise RuntimeError("Missing MONGO_URI or SLACK_BOT_TOKEN in environment variables")

client = MongoClient(MONGO_URI)
db = client["fransa_demo"]
users_col = db["users"]

stt_model = WhisperModel(
    "small",
    device="cpu",        # or "cuda" if you have GPU
    compute_type="int8",  # good tradeoff for CPU
)

AUDIO_FILETYPES = {"mp3", "m4a", "wav", "ogg", "webm", "mp4"}

async def is_audio_file(file_obj: Dict) -> bool:
    mimetype = (file_obj.get("mimetype") or "").lower()
    filetype = (file_obj.get("filetype") or "").lower()
    if mimetype.startswith("audio/"):
        return True
    if filetype in AUDIO_FILETYPES:
        return True
    return False

async def download_slack_file(file_obj: Dict) -> str:
    """
    Download a Slack file to a temporary path and return the path.
    Requires files:read scope and a valid bot token.
    """
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
    """
    Transcribe an audio file using faster-whisper and return the text.
    """
    print(f"[DEBUG] Transcribing audio file at {path}")
    segments, info = stt_model.transcribe(path, beam_size=5)
    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)
    transcript = " ".join(text_parts).strip()
    print(f"[DEBUG] Transcription result: {transcript[:120]}...")
    return transcript or "[unintelligible voice message]"

app = FastAPI(title="Banking Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this later in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

intent_agent = create_intent_agent()
chat_sessions: Dict[str, List[Dict[str, str]]] = {}

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

def send_message_to_slack(channel: str, text: str):
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"channel": channel, "text": text}
    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
    
@app.post("/slack/events")
async def slack_events(request: Request):
    # Handle Slack retries
    if request.headers.get("X-Slack-Retry-Num"):
        retry_num = request.headers.get("X-Slack-Retry-Num")
        reason = request.headers.get("X-Slack-Retry-Reason")
        print(f"[DEBUG] Ignoring Slack retry #{retry_num} (reason: {reason})")
        return {"ok": True}

    data = await request.json()
    print(f"DATA: {data}")
    print(f"\n[DEBUG] Incoming Slack event at {datetime.now()}")
    print(f"[DEBUG] Payload type: {data.get('type')}")

    # URL verification
    if data.get("type") == "url_verification":
        print("[DEBUG] URL verification challenge received.")
        return {"challenge": data["challenge"]}

    # Event callback
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        print(f"[DEBUG] Slack event received: {event.get('type')} | Subtype: {event.get('subtype')}")

        # Ignore missing users or system noise
        if not event.get("user"):
            print("[DEBUG] Ignored event (no user field).")
            return {"ok": True}

        user_id = event["user"]
        channel = event["channel"]
        text = (event.get("text") or "").strip()

        # --- Ignore bot's own messages (DM loops fix) ---
        bot_user_id = os.getenv("SLACK_BOT_USER_ID")
        if user_id == bot_user_id:
            print(f"[DEBUG] Ignoring message from bot itself ({bot_user_id})")
            return {"ok": True}

        # Ignore other bot/system messages
        if event.get("subtype") == "bot_message":
            print("[DEBUG] Ignored bot_message subtype.")
            return {"ok": True}

        print(f"[DEBUG] Raw user message from {user_id} in channel {channel}: '{text}'")

        # Handle file attachments (audio transcription etc.)
        voice_transcript = None
        files = event.get("files") or []
        audio_path = None

        if files:
            print(f"[DEBUG] Event contains {len(files)} file(s)")
        for f in files:
            if not is_audio_file(f):
                continue
            print(f"[DEBUG] Audio file detected: {f.get('id')} {f.get('filetype')}")
            try:
                audio_path = download_slack_file(f)
                voice_transcript = transcribe_audio_file(audio_path)
            except Exception as e:
                print(f"[ERROR] Failed to process audio file: {e}")
            finally:
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
            break

        # Final message content
        agent_input = (
            f"{text}\n\n[Voice message transcript]: {voice_transcript}"
            if voice_transcript and text
            else (voice_transcript or text)
        )

        print(f"[DEBUG] User input to agent: '{agent_input[:120]}...'")

        # Mongo lookup
        user_doc = users_col.find_one({"slack_id": user_id})
        if not user_doc:
            print(f"[DEBUG] Unregistered Slack user {user_id}. Rejecting message.")
            send_message_to_slack(channel, "❌ Unregistered user. Please register your Slack account.")
            return {"ok": False}

        client_id = user_doc.get("clientId")
        auth_token = user_doc.get("authToken")
        print(f"[DEBUG] Authenticated Slack user {user_id} → Mongo clientId {client_id}")

        # Maintain session
        session_id = f"slack_{user_id}"
        chat_sessions.setdefault(session_id, [])
        print(f"[DEBUG] Session loaded: {session_id} | {len(chat_sessions[session_id])} previous messages")

        try:
            print("[DEBUG] Invoking intent agent...")
            result = intent_agent.invoke({
                "user_input": agent_input,
                "conversation_history": chat_sessions[session_id],
                "clientId": client_id,
                "slack_user_id": user_id
            })
            print("[DEBUG] Intent agent returned successfully.")

            response_text = result.get("result", {}).get("content", "No response")
            chat_sessions[session_id] = result.get("conversation_history", [])
            print(f"[DEBUG] Response ready: {response_text[:80]}...")
        except Exception as e:
            print(f"[ERROR] Slack event processing failed: {e}")
            send_message_to_slack(channel, f"⚠️ Error: {str(e)}")
            return {"ok": False}

        print(f"[DEBUG] Sending reply back to Slack channel {channel}")
        send_message_to_slack(channel, response_text)

    print("[DEBUG] Slack event processed successfully.")
    return {"ok": True}

@app.post("/chat", response_model=ChatResponse)
async def chat(chat_message: ChatMessage):
    try:
        session_id = chat_message.session_id or f"session_{datetime.now().timestamp()}"
        chat_sessions.setdefault(session_id, [])
        conversation_history = chat_sessions[session_id]

        result = intent_agent.invoke({
            "user_input": chat_message.message,
            "conversation_history": conversation_history,
            "clientId": chat_message.clientId,
        })

        updated_history = result.get("conversation_history", [])
        chat_sessions[session_id] = updated_history

        print(f"[DEBUG] Chat session {session_id}, messages: {len(updated_history)}")

        return ChatResponse(
            response=result["result"]["content"],
            intent=result["intent"],
            session_id=session_id,
            conversation_history=updated_history
        )

    except Exception as e:
        print(f"[ERROR] /chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

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
    return {
        "sessions": [
            {"session_id": sid, "message_count": len(history)}
            for sid, history in chat_sessions.items()
        ]
    }

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Banking Assistant API!", "status": "running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
