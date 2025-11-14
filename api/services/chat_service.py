import os
from pymongo import MongoClient
from user_context import UserDataContext
from api.services.intent_service import IntentService
from api.services.session_service import SessionService
from api.models.pydantic_models import ChatMessage, ChatResponse, SessionResponse

class ChatService:
    def __init__(self):
        self.intent = IntentService()
        self.sessions = SessionService()

        mongo = MongoClient(os.getenv("MONGO_URI"))
        db = mongo["fransa_demo"]
        self.cards = db["cards"]
        self.transactions = db["transactions"]

    async def handle_chat(self, msg: ChatMessage) -> ChatResponse:
        user_ctx = UserDataContext(msg.clientId, self.cards, self.transactions)

        session_id = msg.session_id or f"session_{os.urandom(8).hex()}"
        history = self.sessions.get(session_id)

        result = self.intent.run(
            user_input=msg.message,
            conversation_history=history,
            clientId=msg.clientId,
            user_ctx=user_ctx,
        )

        self.sessions.set(session_id, result["conversation_history"])

        return ChatResponse(
            response=result["result"]["content"],
            intent=result["intent"],
            session_id=session_id,
            conversation_history=result["conversation_history"],
        )

    def new_session(self):
        return SessionResponse(session_id=f"session_{os.urandom(8).hex()}", conversation_history=[])

    def get_session(self, session_id: str):
        return SessionResponse(session_id=session_id, conversation_history=self.sessions.get(session_id))

    def clear_session(self, session_id: str):
        self.sessions.set(session_id, [])
        return {"message": "Session cleared", "session_id": session_id}

    def list_sessions(self):
        return self.sessions.list()
