from typing import Dict, Any
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama
from prompts.banking_prompt import banking_prompt
from agents.intentAgent import create_intent_agent
from dotenv import load_dotenv
import os
load_dotenv()

from tools.mcptools import (
    change_pin_tool,
    view_card_details_tool,
    list_recent_transactions_tool,
    list_transactions_date_range_tool,
)

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
def banking_llm_agent(state: MessagesState) -> Dict[str, Any]:
    """
    Core node: takes messages and returns an AI message
    that may include tool calls. Injects the system prompt
    if not already present.
    """
    messages = state["messages"]
    print(messages)  # debug

    def get_role(m):
        # Handle LangChain message objects (HumanMessage, SystemMessage, etc.)
        if hasattr(m, "type"):
            # LangChain uses .type not .role
            if m.type == "human":
                return "user"
            elif m.type == "ai":
                return "assistant"
            elif m.type == "system":
                return "system"
            return m.type
        # Handle plain dicts
        return m.get("role") if isinstance(m, dict) else None

    def get_content(m):
        if hasattr(m, "content"):
            return m.content
        if isinstance(m, dict):
            return m.get("content")
        return None

    # Inject system prompt if missing
    if not any(get_role(m) == "system" for m in messages):
        user_msg = next((m for m in messages if get_role(m) == "user"), None)
        if user_msg:
            system_msg = {
                "role": "system",
                "content": banking_prompt()
            }
            messages = [system_msg] + messages

    ai_msg = LLM.invoke(messages)
    return {"messages": messages + [ai_msg]}

# 4. Router function to decide if we should use tools or end
def should_continue(state: MessagesState) -> str:
    """
    Determines whether to continue to tool execution or end.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message has tool calls, route to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    # Otherwise, end the conversation
    return "end"

# 5. Build graph
def create_banking_agent():
    builder = StateGraph(MessagesState)
    
    # Add nodes
    builder.add_node("card_llm_agent", banking_llm_agent)
    builder.add_node("tools", tool_node)
    
    # Add edges
    builder.add_edge(START, "card_llm_agent")
    
    # Add conditional edge from agent
    builder.add_conditional_edges(
        "card_llm_agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # After tools are executed, go back to the agent
    builder.add_edge("tools", "card_llm_agent")
    
    return builder.compile()


# 6. Run agent
if __name__ == "__main__":
    agent = create_banking_agent()
    user_message = {"role": "user", "content": "Show my last 3 transactions."}
    result = agent.invoke({"messages": [user_message]})
    
    # Print the final response
    print("\n=== Final Response ===")
    final_message = result["messages"][-1]
    print(final_message.content if hasattr(final_message, "content") else final_message)
