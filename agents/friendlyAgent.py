from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os
from prompts.friendly_prompt import friendly_prompt
load_dotenv()

def create_friendly_agent():
    llm = ChatOllama(model=os.getenv("MODEL_NAME"), temperature=0.8)

    def respond(user_input: str) -> str:
        prompt = friendly_prompt(user_input)
        response = llm.invoke(prompt)
        return response.content.strip()

    return {"invoke": lambda state: {"messages": [{"content": respond(state['user_input'])}]}}
