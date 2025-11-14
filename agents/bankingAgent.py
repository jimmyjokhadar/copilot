import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode
from tools.mcptools import build_banking_tools
from prompts.banking_prompt import banking_prompt
from langgraph.graph import MessagesState, StateGraph, START, END

load_dotenv()
logger = logging.getLogger(__name__)

class BankingAgent:
    """
    An agent for handling banking-related queries using LLMs and tools.
    1. Initializes with user context and builds banking tools.
    2. Defines an LLM node to process messages and add system prompts if missing.
    3. Implements a router to decide whether to continue with tool calls or end.
    4. Constructs a state graph connecting the LLM and tool nodes.
    """
    def __init__(self, user_ctx: Dict[str, Any]):
        self.user_ctx = user_ctx
        self.tools = build_banking_tools(user_ctx)
        self.llm = ChatOllama(
            model=os.getenv("MODEL_NAME"),
            temperature=0
        ).bind_tools(self.tools)


    def llm_node(self, state: MessagesState):
        """
        LLM NODE: Processes messages and adds system prompt if missing.
        Args:
            state (MessagesState): The current state containing messages.
        Returns:
            MessagesState: Updated state with LLM response.
        """
        messages = state["messages"]
        logger.debug(f"LLM Node received messages: {messages}")
        if not any(m.get("role") == "system" for m in messages if isinstance(m, dict)):
            system_msg = {"role": "system", "content": banking_prompt()}
            messages = [system_msg] + messages

        ai_msg = self.llm.invoke(messages)
        logger.debug(f"LLM response: {ai_msg}")
        return {"messages": messages + [ai_msg]}


    def should_continue(self, state: MessagesState) -> str:
        """
        ROUTER: Decides whether to continue with tool calls or end.
        Args:
            state (MessagesState): The current state containing messages.
        Returns:
            str: Next node identifier ("tools" or "end").
        """
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"


    def build(self):
        """
        Constructs the state graph for the banking agent.
        Returns:
            StateGraph: The constructed state graph.
        """
        builder = StateGraph(MessagesState)

        builder.add_node("llm", self.llm_node)
        builder.add_node("tools", ToolNode(self.tools))

        builder.add_edge(START, "llm")
        builder.add_conditional_edges(
            "llm",
            self.should_continue,
            {"tools": "tools", "end": END}
        )
        builder.add_edge("tools", "llm")

        return builder.compile()