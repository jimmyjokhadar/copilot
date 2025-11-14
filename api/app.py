from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controllers.slack_controller import SlackController
from controllers.chat_controller import ChatController

app = FastAPI(title="Banking Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

slack = SlackController()
chat = ChatController()

app.include_router(slack.router, prefix="/slack")
app.include_router(chat.router, prefix="/chat")


@app.get("/")
async def root():
    return {"message": "Welcome to the Banking Assistant API!", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
