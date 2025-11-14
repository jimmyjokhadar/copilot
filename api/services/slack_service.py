import os
import requests
import tempfile
from fastapi import Request
from dotenv import load_dotenv
from pymongo import MongoClient
#from user_context import UserDataContext
from services.slack_utils import SlackUtils
from services.stt_service import STTService
from services.intent_service import IntentService
from services.session_service import SessionService

load_dotenv()

class SlackService:
    def __init__(self):
        self.intent = IntentService()
        self.sessions = SessionService()
        self.stt = STTService()
        self.slack = SlackUtils()

        mongo = MongoClient(os.getenv("MONGO_URI"))
        db = mongo["fransa_demo"]
        self.users = db["users"]
        self.cards = db["cards"]
        self.transactions = db["transactions"]

    async def process_event(self, request: Request):
        data = await request.json()

        if request.headers.get("X-Slack-Retry-Num"):
            return {"ok": True}

        if data.get("type") == "url_verification":
            return {"challenge": data["challenge"]}

        if data.get("type") != "event_callback":
            return {"ok": True}

        event = data["event"]

        if event.get("subtype") == "bot_message":
            return {"ok": True}

        user_id = event["user"]
        channel = event["channel"]
        text = (event.get("text") or "").strip()

        # audio attachment handling
        files = event.get("files", [])
        if files:
            audio = next((f for f in files if self.stt.is_audio_file(f)), None)
            if audio:
                try:
                    text = self.stt.transcribe_remote_file(audio)
                except Exception as e:
                    self.slack.send_message(channel, f"Audio processing failed: {e}")
                    return {"ok": True}

        if not text:
            return {"ok": True}

        user_doc = self.users.find_one({"slack_id": user_id})
        if not user_doc:
            return {"ok": True}

        client_id = user_doc.get("clientId")
        if not client_id:
            self.slack.send_message(channel, "Missing client ID.")
            return {"ok": True}

        ##user_ctx = UserDataContext(client_id, self.cards, self.transactions)

        session_id = f"slack_{user_id}"
        history = self.sessions.get(session_id)

        result = self.intent.run(
            user_input=text,
            conversation_history=history,
            slack_user_id=user_id,
            clientId=client_id,
            user_ctx=None,
        )

        self.sessions.set(session_id, result["conversation_history"])
        self.slack.send_message(channel, result["result"]["content"])

        return {"ok": True}
