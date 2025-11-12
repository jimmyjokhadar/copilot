from typing import TypedDict, Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from prompts.intent_prompt import intent_prompt
from dotenv import load_dotenv
import os

load_dotenv()

# === State Definition ===
class IntentState(TypedDict):
    user_input: str
    intent: str | None
    result: Dict[str, Any] | None
    conversation_history: List[Dict[str, str]]
    context: str | None  # e.g. "banking_in_progress"

# === Initialize LLM ===
llm = ChatOllama(model=os.getenv("MODEL_NAME"), temperature=0)

# === Intent Detector Node ===
def intent_detector(state: IntentState) -> IntentState:
    user_input = state["user_input"]
    conversation_history = state.get("conversation_history", [])

    # Detect whether we’re in a banking context based on previous assistant replies
    in_banking_context = False
    for msg in reversed(conversation_history):
        if msg.get("role") == "assistant":
            content_lower = msg.get("content", "").lower()
            if any(
                word in content_lower
                for word in ["card", "pin", "transaction", "balance", "which card", "provide"]
            ):
                in_banking_context = True
            break

    # Lightweight heuristic: short / numeric input in banking context → "customer_request"
    if in_banking_context and (user_input.replace(" ", "").isdigit() or len(user_input.split()) <= 3):
        intent = "customer_request"
    else:
        # NO clientId here, pure text-based intent classification
        prompt = intent_prompt(user_input)
        response = llm.invoke(prompt)
        intent = response.content.strip().lower()

    return {
        "user_input": user_input,
        "intent": intent,
        "result": None,
        "conversation_history": conversation_history,
        "context": state.get("context"),
    }

# === Banking Node ===
def banking_node(state: IntentState) -> IntentState:
    from agents.bankingAgent import create_banking_agent

    # For now: banking_agent is still global (we'll refactor it to accept user_ctx later)
    banking_agent = create_banking_agent()
    conversation_history = state.get("conversation_history", [])

    # No [clientId=...] prefix anymore
    user_message = {"role": "user", "content": state["user_input"]}
    messages = conversation_history + [user_message]

    # Invoke banking agent
    result = banking_agent.invoke({"messages": messages})
    final_message = result["messages"][-1]
    content = getattr(final_message, "content", str(final_message))

    updated_history = conversation_history + [
        user_message,
        {"role": "assistant", "content": content},
    ]

    tool_executed = False
    if hasattr(result, "tool_calls"):
        tool_executed = len(result.tool_calls) > 0
    elif isinstance(result, dict) and "tool_calls" in result:
        tool_executed = bool(result["tool_calls"])

    # --- Determine context based on tool call ---
    if tool_executed:
        context = None  # done, task completed
    else:
        context = "banking_in_progress"  # still gathering info

    return {
        "user_input": state["user_input"],
        "intent": state["intent"],
        "result": {"type": "banking_response", "content": content},
        "conversation_history": updated_history,
        "context": context,
    }

# === Fallback Node ===
def fallback_node(state: IntentState) -> IntentState:
    conversation_history = state.get("conversation_history", [])
    fallback_msg = "I'm sorry, I can only assist with banking-related queries."

    updated_history = conversation_history + [
        {"role": "user", "content": state["user_input"]},
        {"role": "assistant", "content": fallback_msg},
    ]

    return {
        "user_input": state["user_input"],
        "intent": state["intent"],
        "result": {"type": "fallback_response", "content": fallback_msg},
        "conversation_history": updated_history,
        "context": state.get("context"),
    }

# === Router ===
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

    def route_entry(state: IntentState):
        if state.get("context") == "banking_in_progress":
            return "banking_node"
        return "intent_detector"

    builder.add_conditional_edges(START, route_entry)
    builder.add_conditional_edges("intent_detector", route_by_intent)
    builder.add_edge("banking_node", END)
    builder.add_edge("fallback_node", END)
    return builder.compile()

# === Test Run ===
if __name__ == "__main__":
    agent = create_intent_agent()
    test_state: IntentState = {
        "user_input": "<@U09S9M6TA81> Show my transactions.",
        "intent": None,
        "result": None,
        "conversation_history": [],
        "context": None,
    }
    result = agent.invoke(test_state)
    print("\n=== Final Output ===")
    print("Detected Intent:", result["intent"])
    print("Response:", result["result"]["content"])
