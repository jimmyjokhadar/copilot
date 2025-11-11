from typing import Dict, Any
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama
from prompts.banking_prompt import banking_prompt
from agents.intentAgent import create_intent_agent
from dotenv import load_dotenv
import os
import re 
import pymongo
load_dotenv()

from tools.mcptools import (
    change_pin_tool,
    view_card_details_tool,
    list_recent_transactions_tool,
    list_transactions_date_range_tool,
)

mongo_uri = os.getenv("MONGO_URI")
mongoClient = pymongo.MongoClient(mongo_uri)
database = mongoClient["fransa_demo"]
collection = database["users"]

# 1. Define tools
TOOLS = [
    change_pin_tool,
    view_card_details_tool,
    list_recent_transactions_tool,
    list_transactions_date_range_tool,
]

# 2. Bind tools to LLM
LLM = ChatOllama(model=os.getenv("MODEL_NAME"), temperature=0).bind_tools(TOOLS)

# 3. Create tool execution node
tool_node = ToolNode(TOOLS)
import re

def banking_llm_agent(state: MessagesState) -> Dict[str, Any]:
    messages = state["messages"]
    print(f"[DEBUG] banking_llm_agent received {messages}")

    # Try to extract Slack ID pattern like <@U09S9M6TA81>
    slack_id = None
    for m in messages:
        if hasattr(m, "content"):
            match = re.search(r"<@([A-Z0-9]+)>", m.content)
        elif isinstance(m, dict) and "content" in m:
            match = re.search(r"<@([A-Z0-9]+)>", m["content"])
        else:
            match = None
        if match:
            slack_id = match.group(1)
            break
    print(f"[DEBUG] Extracted slack_id: {slack_id}")
    client_id = None
    try:
        if slack_id:
            user_doc = collection.find_one({"slack_id": slack_id})
            if user_doc and "clientId" in user_doc:
                client_id = user_doc["clientId"]
                print(f"[DEBUG] Retrieved clientId={client_id} for Slack user {slack_id}")
            else:
                print(f"[DEBUG] No matching clientId found for Slack ID {slack_id}")
        else:
            print("[DEBUG] No Slack ID mention found in message content")
    except Exception as e:
        print(f"[ERROR] Mongo lookup failed: {e}")

    print(f"[DEBUG] banking_llm_agent invoked for clientId={client_id}")

    if not any(
        (hasattr(m, "type") and m.type == "system")
        or (isinstance(m, dict) and m.get("role") == "system")
        for m in messages
    ):
        system_msg = {
            "role": "system",
            "content": banking_prompt(client_id)
        }
        messages = [system_msg] + messages

    ai_msg = LLM.invoke(messages)
    return {"messages": messages + [ai_msg]}

# 4. Router function to decide if we should use tools or end
def should_continue(state: MessagesState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

# 5. Build graph
def create_banking_agent():
    builder = StateGraph(MessagesState)
    builder.add_node("card_llm_agent", banking_llm_agent)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "card_llm_agent")
    builder.add_conditional_edges(
        "card_llm_agent",
        should_continue,
        {"tools": "tools", "end": END}
    )
    builder.add_edge("tools", "card_llm_agent")
    return builder.compile()

# 6. Run agent
if __name__ == "__main__":
    agent = create_banking_agent()
    user_message = {"role": "user", "content": "Show my last 3 transactions."}
    result = agent.invoke({"messages": [user_message]})
    print("\n=== Final Response ===")
    final_message = result["messages"][-1]
    print(final_message.content if hasattr(final_message, "content") else final_message)