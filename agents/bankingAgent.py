from typing import Dict, Any
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama
from prompts.banking_prompt import banking_prompt
from dotenv import load_dotenv
import os
from tools.mcptools import (
    change_pin_tool,
    view_card_details_tool,
    list_recent_transactions_tool,
    list_transactions_date_range_tool,
)

load_dotenv()

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


def banking_llm_agent(state: MessagesState) -> Dict[str, Any]:
    messages = state["messages"]

    # Ensure there is a system message; do NOT inject clientId anymore
    has_system = any(
        (hasattr(m, "type") and m.type == "system")
        or (isinstance(m, dict) and m.get("role") == "system")
        for m in messages
    )

    if not has_system:
        system_msg = {
            "role": "system",
            # IMPORTANT: banking_prompt() must be updated to NOT require clientId
            "content": banking_prompt(),
        }
        messages = [system_msg] + messages
        print(f"[DEBUG] System Prompt: {system_msg['content'][:120]}...")

    # Normal LLM + tools call
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
        {"tools": "tools", "end": END},
    )
    builder.add_edge("tools", "card_llm_agent")
    return builder.compile()


# 6. Run agent (manual test)
if __name__ == "__main__":
    agent = create_banking_agent()
    user_message = {"role": "user", "content": "Show my last 3 transactions."}
    result = agent.invoke({"messages": [user_message]})
    print("\n=== Final Response ===")
    final_message = result["messages"][-1]
    print(final_message.content if hasattr(final_message, "content") else final_message)
