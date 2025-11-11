from typing import TypedDict, Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from prompts.intent_prompt import intent_prompt
from dotenv import load_dotenv
import os
import pymongo

load_dotenv()

# === Mongo Setup ===
mongo_uri = os.getenv("MONGO_URI")
mongoClient = pymongo.MongoClient(mongo_uri)
database = mongoClient["fransa_demo"]
collection = database["users"]

# === State Definition ===
class IntentState(TypedDict):
    user_input: str
    intent: str | None
    result: Dict[str, Any] | None
    conversation_history: List[Dict[str, str]]
    clientId: str | None
    slack_user_id: str | None  # add actual Slack user
    context: str | None  # optional context field

# === Extractor ===
def get_client_id_from_slack_user(slack_user_id: str | None) -> str | None:
    """Lookup clientId directly from MongoDB via Slack user ID."""
    if not slack_user_id:
        print("[DEBUG] No Slack user ID provided to lookup.")
        return None

    user_doc = collection.find_one({"slack_id": slack_user_id})
    if user_doc and "clientId" in user_doc:
        print(f"[DEBUG] Slack user {slack_user_id} → clientId {user_doc['clientId']}")
        return user_doc["clientId"]

    print(f"[DEBUG] No clientId found for Slack user {slack_user_id}")
    return None

# === Initialize LLM ===
llm = ChatOllama(model=os.getenv("MODEL_NAME"), temperature=0)

# === Intent Detector Node ===
def intent_detector(state: IntentState) -> IntentState:
    user_input = state["user_input"]
    conversation_history = state.get("conversation_history", [])
    slack_user_id = state.get("slack_user_id")

    # Get clientId from slack_user_id or fallback
    client_id = state.get("clientId") or get_client_id_from_slack_user(slack_user_id)

    # Detect whether we’re in a banking context
    in_banking_context = False
    for msg in reversed(conversation_history):
        if msg.get("role") == "assistant":
            content_lower = msg.get("content", "").lower()
            if any(word in content_lower for word in ["card", "pin", "transaction", "balance", "which card", "provide"]):
                in_banking_context = True
            break

    # Intent classification
    if in_banking_context and (user_input.replace(" ", "").isdigit() or len(user_input.split()) <= 3):
        intent = "customer_request"
    else:
        prompt = intent_prompt(user_input, client_id)
        response = llm.invoke(prompt)
        intent = response.content.strip().lower()

    return {
        "user_input": user_input,
        "intent": intent,
        "result": None,
        "conversation_history": conversation_history,
        "clientId": client_id,
        "slack_user_id": slack_user_id,
    }

# === Banking Node ===
def banking_node(state: IntentState) -> IntentState:
    from agents.bankingAgent import create_banking_agent

    banking_agent = create_banking_agent()
    client_id = state.get("clientId")
    conversation_history = state.get("conversation_history", [])

    # Add message with clientId included
    user_message = {"role": "user", "content": f"[clientId={client_id}] {state['user_input']}"}
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
        "clientId": client_id,
        "slack_user_id": state.get("slack_user_id"),
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
        "clientId": state.get("clientId"),
        "slack_user_id": state.get("slack_user_id"),
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
    # simulate Slack event (sender vs. mention)
    test_state = {
        "user_input": "<@U09S9M6TA81> Show my transactions.",
        "slack_user_id": "U09SRT9331N",  # real sender
    }
    result = agent.invoke(test_state)
    print("\n=== Final Output ===")
    print("Detected Intent:", result["intent"])
    print("Client ID:", result["clientId"])
    print("Response:", result["result"]["content"])
