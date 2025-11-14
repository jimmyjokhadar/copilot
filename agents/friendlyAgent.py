from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os
from prompts.friendly_prompt import friendly_prompt
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class FriendlyAgent:
    def __init__(self, model_name: str = None, temperature: float = 0.8):
        model_name = model_name or os.getenv("MODEL_NAME")
        logger.debug(f"Initializing FriendlyAgent with model: {model_name}")
        if not model_name:
            logger.error("MODEL_NAME environment variable is not set.")
            raise RuntimeError("MODEL_NAME is missing")

        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature
        )

    def _build_prompt(self, user_input: str) -> str:
        return friendly_prompt(user_input)

    def respond(self, user_input: str) -> str:
        prompt = self._build_prompt(user_input)
        response = self.llm.invoke(prompt)
        return response.content.strip()

    def invoke(self, state: dict) -> dict:
        user_input = state.get("user_input")
        if not user_input:
            logger.error("State missing 'user_input'")
            raise ValueError("state missing 'user_input'")
        
        answer = self.respond(user_input)
        logger.debug(f"FriendlyAgent response: {answer}")
        return {
            "messages": [
                {"content": answer}
            ]
        }

