from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    clientId: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    session_id: str
    conversation_history: List[Dict[str, str]]

class SessionResponse(BaseModel):
    session_id: str
    conversation_history: List[Dict[str, str]]
