from typing import Dict, Any
from langgraph.graph import MessagesState, StateGraph, START, END
from langchain_ollama import ChatOllama
from prompts.banking_prompt import banking_prompt

from tools.mcptools import (
    change_pin_tool,
    view_card_details_tool,
    list_recent_transactions_tool
)

# 1. Define tools
TOOLS = [
    change_pin_tool,
    view_card_details_tool,
    list_recent_transactions_tool
]

# 2. Bind tools to LLM
LLM = ChatOllama(model="gpt-oss:latest", temperature=0).bind_tools(TOOLS)
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
                "content": banking_prompt(get_content(user_msg))
            }
            messages = [system_msg] + messages

    ai_msg = LLM.invoke(messages)
    return {"messages": messages + [ai_msg]}

# 4. Build graph
def create_banking_agent():
    builder = StateGraph(MessagesState)
    builder.add_node("card_llm_agent", banking_llm_agent)
    builder.add_edge(START, "card_llm_agent")
    builder.add_edge("card_llm_agent", END)
    return builder.compile()


# 5. Run agent
if __name__ == "__main__":
    agent = create_banking_agent()
    user_message = {"role": "user", "content": "Show my last 3 transactions."}
    result = agent.invoke({"messages": [user_message]})
    print(result)
