from fastapi import APIRouter, Request
from services.slack_service import SlackService

class SlackController:
    def __init__(self):
        self.router = APIRouter()
        self.service = SlackService()

        self.router.post("/events")(self.events)

    async def events(self, request: Request):
        return await self.service.process_event(request)
