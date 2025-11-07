from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from prompts.intent_prompt import intent_prompt
from dotenv import load_dotenv
import os 
load_dotenv()

class IntentState(TypedDict):
    user_input: str
    intent: str | None
    result: Dict[str, Any] | None

# Initialize LLM for intent detection
llm = ChatOllama(model=os.getenv("MODEL_NAME"), temperature=0)

def intent_detector(state: IntentState) -> IntentState:
    user_input = state["user_input"]
    prompt = intent_prompt(user_input)
    response = llm.invoke(prompt)
    intent = response.content.strip().lower()
    return {"user_input": user_input, "intent": intent}

def banking_node(state: IntentState) -> IntentState:
    # Lazy import to avoid circular dependency
    from agents.bankingAgent import create_banking_agent

    banking_agent = create_banking_agent()
    user_message = {"role": "user", "content": state["user_input"]}
    result = banking_agent.invoke({"messages": [user_message]})

    final_message = result["messages"][-1]
    content = getattr(final_message, "content", str(final_message))
    return {"user_input": state["user_input"], "intent": state["intent"], "result": {"type": "banking_response", "content": content}}

def fallback_node(state: IntentState) -> IntentState:
    return {
        "user_input": state["user_input"],
        "intent": state["intent"],
        "result": {"type": "fallback_response", "content": "I'm sorry, I can only assist with banking-related queries."}
    }

def route_by_intent(state: IntentState) -> str:
    intent = state["intent"]
    if intent == "customer_request":
        return "banking_node"
    elif intent in ("general_query", "sql_query"):
        return "fallback_node"
    return "fallback_node"

def create_intent_agent():
    builder = StateGraph(IntentState)

    builder.add_node("intent_detector", intent_detector)
    builder.add_node("banking_node", banking_node)
    builder.add_node("fallback_node", fallback_node)

    builder.add_edge(START, "intent_detector")
    builder.add_conditional_edges("intent_detector", route_by_intent)
    builder.add_edge("banking_node", END)
    builder.add_edge("fallback_node", END)

    return builder.compile()

if __name__ == "__main__":
    agent = create_intent_agent()
    user_input = "Show my last 3 transactions."
    result = agent.invoke({"user_input": user_input})
    print("\n=== Final Output ===")
    print("Detected Intent:", result["intent"])
    print("Response:", result["result"]["content"])
