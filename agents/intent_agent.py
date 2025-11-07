from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from prompts.intent_prompt import intent_prompt


class IntentState(TypedDict):
    user_input: str
    intent: str | None

llm = ChatOllama(model="gpt-oss:latest", temperature=0)


def intent_detector(state: IntentState) -> IntentState:
    user_input = state["user_input"]
    prompt = intent_prompt(user_input)
    response = llm.invoke(prompt)
    return {"intent": response.content}


def create_intent_agent():
    builder = StateGraph(IntentState)
    builder.add_node("intent_detector", intent_detector)
    builder.add_edge(START, "intent_detector")
    builder.add_edge("intent_detector", END)
    return builder.compile()


if __name__ == "__main__":
    agent = create_intent_agent()
    user_input = "Can you show me the balance of customer 1234?"
    result = agent.invoke({"user_input": user_input})
    print("Detected Intent:", result["intent"])
