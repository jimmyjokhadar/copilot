from fastapi import APIRouter, HTTPException
from services.chat_service import ChatService
from models.pydantic_models import ChatMessage, ChatResponse, SessionResponse

class ChatController:
    def __init__(self):
        self.router = APIRouter()
        self.service = ChatService()

        self.router.post("")(self.chat)
        self.router.post("/new")(self.new)
        self.router.get("/session/{session_id}")(self.get_session)
        self.router.delete("/session/{session_id}")(self.clear_session)
        self.router.get("/sessions")(self.list_sessions)

    async def chat(self, chat_message: ChatMessage) -> ChatResponse:
        try:
            return await self.service.handle_chat(chat_message)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def new(self):
        return self.service.new_session()

    async def get_session(self, session_id: str):
        return self.service.get_session(session_id)

    async def clear_session(self, session_id: str):
        return self.service.clear_session(session_id)

    async def list_sessions(self):
        return self.service.list_sessions()
