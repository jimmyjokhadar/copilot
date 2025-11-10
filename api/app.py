from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from dotenv import load_dotenv
import requests
import os
from datetime import datetime
from agents.intentAgent import create_intent_agent

load_dotenv()

app = FastAPI(title="Banking Assistant API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the intent agent
intent_agent = create_intent_agent()

# In-memory session storage (use Redis or database in production)
chat_sessions: Dict[str, List[Dict[str, str]]] = {}

# Request/Response Models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    session_id: str
    conversation_history: List[Dict[str, str]]

class SessionResponse(BaseModel):
    session_id: str
    conversation_history: List[Dict[str, str]]

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

def send_message_to_slack(channel: str, text: str):
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"channel": channel, "text": text}
    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)


@app.post("/slack/events")
async def slack_events(request: Request):
    data = await request.json()

    # URL verification
    if data.get("type") == "url_verification":
        return {"challenge": data["challenge"]}

    # Event callback
    if data.get("type") == "event_callback":
        event = data["event"]

        # Ignore bot messages
        if event.get("subtype") == "bot_message" or event.get("user") is None:
            return {"ok": True}

        user_id = event["user"]
        channel = event["channel"]
        text = event.get("text", "")

        # Maintain per-user session
        session_id = f"slack_{user_id}"
        chat_sessions.setdefault(session_id, [])

        # Process message through intent agent
        result = intent_agent.invoke({
            "user_input": text,
            "conversation_history": chat_sessions[session_id]
        })

        response_text = result["result"]["content"]
        chat_sessions[session_id] = result.get("conversation_history", [])

        # Send reply to Slack
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {"channel": channel, "text": response_text}
        requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)

    return {"ok": True}



@app.get("/")
def read_root():
    return {"message": "Welcome to the Banking Assistant API!", "status": "running", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(chat_message: ChatMessage):
    """
    Send a message to the intent agent and get a response.
    Maintains conversation history per session.
    
    IMPORTANT: Always provide the same session_id to maintain conversation context.
    If no session_id is provided, a new session will be created.
    """
    try:
        # Get or create session
        if chat_message.session_id:
            # Use existing session
            session_id = chat_message.session_id
            # Initialize session if it doesn't exist
            if session_id not in chat_sessions:
                chat_sessions[session_id] = []
            conversation_history = chat_sessions[session_id]
        else:
            # Create new session only if no session_id provided
            session_id = f"session_{datetime.now().timestamp()}"
            chat_sessions[session_id] = []
            conversation_history = []
        
        # Process the message through the intent agent
        result = intent_agent.invoke({
            "user_input": chat_message.message,
            "conversation_history": conversation_history
        })
        
        # Update session history from the result
        # The intent agent returns updated conversation_history in the result
        updated_history = result.get("conversation_history", [])
        chat_sessions[session_id] = updated_history
        
        print(f"[DEBUG] Updated history length: {len(updated_history)}")
        print(f"[DEBUG] Response: {result['result']['content'][:100]}...")
        
        return ChatResponse(
            response=result["result"]["content"],
            intent=result["intent"],
            session_id=session_id,
            conversation_history=updated_history
        )
    
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@app.post("/chat/new", response_model=SessionResponse)
async def new_chat_session():
    """
    Create a new chat session with empty conversation history.
    """
    session_id = f"session_{datetime.now().timestamp()}"
    chat_sessions[session_id] = []
    
    return SessionResponse(
        session_id=session_id,
        conversation_history=[]
    )

@app.get("/chat/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """
    Retrieve conversation history for a specific session.
    """
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        session_id=session_id,
        conversation_history=chat_sessions[session_id]
    )

@app.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear the conversation history for a specific session.
    """
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    chat_sessions[session_id] = []
    
    return {"message": "Session cleared successfully", "session_id": session_id}

@app.get("/chat/sessions")
async def list_sessions():
    """
    List all active chat sessions.
    """
    return {
        "sessions": [
            {
                "session_id": sid,
                "message_count": len(history)
            }
            for sid, history in chat_sessions.items()
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)