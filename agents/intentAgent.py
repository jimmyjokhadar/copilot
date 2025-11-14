import os
import logging
import pymongo
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from typing import TypedDict, Dict, Any, List
from prompts.intent_prompt import intent_prompt
from langgraph.graph import StateGraph, START, END
from agents.bankingAgent import create_banking_agent

load_dotenv()
logger = logging.getLogger(__name__)


class IntentState(TypedDict):
    user_input: str
    intent: str | None
    result: Dict[str, Any] | None
    conversation_history: List[Dict[str, str]]
    clientId: str | None
    slack_user_id: str | None
    context: str | None
    user_ctx: Any | None


class IntentAgent:
    def __init__(self, user_ctx):
        """Initialize agent with models, DB, and user context."""
        self.user_ctx = user_ctx

        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            logger.error("MONGO_URI environment variable is not set.")
            raise RuntimeError("Missing MONGO_URI")

        self.mongo = pymongo.MongoClient(mongo_uri)["fransa_demo"]
        self.users = self.mongo["users"]

        model_name = os.getenv("MODEL_NAME")
        if not model_name:
            logger.error("MODEL_NAME environment variable is not set.")
            raise RuntimeError("Missing MODEL_NAME")

        self.llm = ChatOllama(model=model_name, temperature=0)
        self.graph = self._build_graph()

    def _get_client_id(self, slack_user_id: str | None) -> str | None:
        """Return clientId linked to a Slack user."""
        if not slack_user_id:
            return None
        doc = self.users.find_one({"slack_id": slack_user_id})
        logger.debug(f"Lookup for Slack ID {slack_user_id}: found doc {doc}")
        return doc.get("clientId") if doc else None

    def _intent_detector(self, state: IntentState) -> IntentState:
        """Detect intent from user input."""
        user_input = state["user_input"]
        slack = state.get("slack_user_id")
        client_id = state.get("clientId") or self._get_client_id(slack)

        prompt = intent_prompt(user_input)
        response = self.llm.invoke(prompt)
        intent = response.content.strip().lower()

        return {
            "user_input": user_input,
            "intent": intent,
            "result": None,
            "conversation_history": state.get("conversation_history", []),
            "clientId": client_id,
            "slack_user_id": slack,
            "context": None,
            "user_ctx": self.user_ctx
        }

    def _banking_node(self, state: IntentState) -> IntentState:
        """Execute banking flow."""
        banking = create_banking_agent(self.user_ctx)

        history = state.get("conversation_history", [])
        user_msg = {"role": "user", "content": state["user_input"]}
        messages = history + [user_msg]

        result = banking.invoke({"messages": messages})
        final_msg = result["messages"][-1]
        content = getattr(final_msg, "content", str(final_msg))

        updated_history = history + [
            user_msg,
            {"role": "assistant", "content": content}
        ]

        return {
            "user_input": state["user_input"],
            "intent": state["intent"],
            "result": {"type": "banking_response", "content": content},
            "conversation_history": updated_history,
            "clientId": state.get("clientId"),
            "slack_user_id": state.get("slack_user_id"),
            "context": None,
            "user_ctx": self.user_ctx
        }

    def _friendly_node(self, state: IntentState) -> IntentState:
        """Execute friendly small-talk flow."""
        from agents.friendlyAgent import create_friendly_agent

        agent = create_friendly_agent()
        result = agent.invoke(state)
        content = result["messages"][-1]["content"]

        history = state.get("conversation_history", [])
        updated = history + [
            {"role": "user", "content": state["user_input"]},
            {"role": "assistant", "content": content}
        ]

        return {
            "user_input": state["user_input"],
            "intent": state["intent"],
            "result": {"type": "friendly_response", "content": content},
            "conversation_history": updated,
            "clientId": state.get("clientId"),
            "slack_user_id": state.get("slack_user_id"),
            "context": None,
            "user_ctx": self.user_ctx
        }

    def _fallback_node(self, state: IntentState) -> IntentState:
        """Return fallback response for unsupported intents."""
        msg = "I'm sorry, I can only assist with banking-related queries."

        history = state.get("conversation_history", [])
        updated = history + [
            {"role": "user", "content": state["user_input"]},
            {"role": "assistant", "content": msg}
        ]

        return {
            "user_input": state["user_input"],
            "intent": state["intent"],
            "result": {"type": "fallback_response", "content": msg},
            "conversation_history": updated,
            "clientId": state.get("clientId"),
            "slack_user_id": state.get("slack_user_id"),
            "context": None,
            "user_ctx": self.user_ctx
        }

    def _route_by_intent(self, state: IntentState) -> str:
        """Return node name based on intent."""
        intent = state["intent"]
        if intent == "customer_request":
            return "banking"
        if intent == "friendly_chat":
            return "friendly"
        if intent in ("general_query", "sql_query"):
            return "fallback"
        return "fallback"

    def _build_graph(self):
        """Construct and compile the LangGraph state machine."""
        g = StateGraph(IntentState)

        g.add_node("intent", self._intent_detector)
        g.add_node("banking", self._banking_node)
        g.add_node("friendly", self._friendly_node)
        g.add_node("fallback", self._fallback_node)

        def route_entry(state: IntentState):
            if state.get("context") == "banking_in_progress":
                return "banking"
            return "intent"

        g.add_conditional_edges(START, route_entry)
        g.add_conditional_edges("intent", self._route_by_intent)
        g.add_edge("banking", END)
        g.add_edge("friendly", END)
        g.add_edge("fallback", END)

        return g.compile()

    def invoke(self, state: IntentState):
        """Run the graph for the given state."""
        return self.graph.invoke(state)


def create_intent_agent(user_ctx):
    """Factory to create IntentAgent."""
    return IntentAgent(user_ctx)
