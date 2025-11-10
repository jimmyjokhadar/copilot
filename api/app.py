from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
import requests
import os
from datetime import datetime
from agents.intentAgent import create_intent_agent

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

if not MONGO_URI or not SLACK_BOT_TOKEN:
    raise RuntimeError("Missing MONGO_URI or SLACK_BOT_TOKEN in environment variables")

client = MongoClient(MONGO_URI)
db = client["fransa_demo"]
users_col = db["users"]

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
    print(f"\n[DEBUG] Incoming Slack event at {datetime.now()}")
    print(f"[DEBUG] Payload type: {data.get('type')}")
    
    # URL verification handshake
    if data.get("type") == "url_verification":
        print("[DEBUG] URL verification challenge received.")
        return {"challenge": data["challenge"]}

    # Event callback
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        print(f"[DEBUG] Slack event received: {event.get('type')} | Subtype: {event.get('subtype')}")

        # Ignore bot messages and system noise
        if event.get("subtype") == "bot_message" or not event.get("user"):
            print("[DEBUG] Ignored event (bot message or missing user).")
            return {"ok": True}

        user_id = event["user"]
        channel = event["channel"]
        text = event.get("text", "").strip()

        print(f"[DEBUG] User message from {user_id} in channel {channel}: '{text}'")

        # Lookup Mongo user linked to this Slack ID
        user_doc = users_col.find_one({"slack_id": user_id})
        if not user_doc:
            print(f"[DEBUG] Unregistered Slack user {user_id}. Rejecting message.")
            send_message_to_slack(channel, "❌ Unregistered user. Please register your Slack account.")
            return {"ok": False}

        client_id = user_doc.get("clientId")
        auth_token = user_doc.get("authToken")

        print(f"[DEBUG] Authenticated Slack user {user_id} → Mongo clientId {client_id}")

        # Maintain per-user chat session
        session_id = f"slack_{user_id}"
        chat_sessions.setdefault(session_id, [])
        print(f"[DEBUG] Session loaded: {session_id} | {len(chat_sessions[session_id])} previous messages")

        # Process message through the intent agent
        try:
            print("[DEBUG] Invoking intent agent...")
            result = intent_agent.invoke({
                "user_input": text,
                "conversation_history": chat_sessions[session_id],
                "clientId": client_id,
                "authToken": auth_token
            })
            print("[DEBUG] Intent agent returned successfully.")

            response_text = result.get("result", {}).get("content", "No response")
            chat_sessions[session_id] = result.get("conversation_history", [])
            print(f"[DEBUG] Response ready: {response_text[:80]}...")  # truncate to 80 chars

        except Exception as e:
            print(f"[ERROR] Slack event processing failed: {e}")
            send_message_to_slack(channel, f"⚠️ Error: {str(e)}")
            return {"ok": False}

        # Send reply to Slack
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
            "authToken": chat_message.authToken
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
def read_root():
    return {"message": "Welcome to the Banking Assistant API!", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
