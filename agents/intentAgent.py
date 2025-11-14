import os
import logging
import pymongo
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from typing import TypedDict, Dict, Any, List
from agents.friendlyAgent import FriendlyAgent
from prompts.intent_prompt import intent_prompt
from langgraph.graph import StateGraph, START, END

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
    """
    An agent to detect user intent and route to appropriate sub-agents.
    1. Initializes with user context and connects to MongoDB for user data.
    2. Defines intent detection, banking, friendly chat, and fallback nodes.
    3. Routes based on detected intent to the corresponding node.
    4. Constructs a state graph connecting these nodes.
    """
    def __init__(self, user_ctx):
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
        """
        Return clientId linked to a Slack user.
        Args:
            slack_user_id (str | None): The Slack user ID.
        Returns:
            str | None: The associated clientId or None if not found.
        """
        if not slack_user_id:
            return None
        doc = self.users.find_one({"slack_id": slack_user_id})
        logger.debug(f"Lookup for Slack ID {slack_user_id}: found doc {doc}")
        return doc.get("clientId") if doc else None

    def _intent_detector(self, state: IntentState) -> IntentState:
        """
        Detect intent from user input.
        Args:
            state (IntentState): The current state containing user input.
        Returns:
            IntentState: Updated state with detected intent.
        """
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
        """
        Execute banking-related flow.
        Args:
            state (IntentState): The current state containing user input.
        Returns:
            IntentState: Updated state with banking response.
        """
        from agents.bankingAgent import BankingAgent
        
        banking = BankingAgent(self.user_ctx)

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
        """
        Execute friendly chat flow.
        Args:
            state (IntentState): The current state containing user input.
        Returns:
            IntentState: Updated state with friendly response.
        """

        agent = FriendlyAgent()
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
        """
        Return fallback response for unsupported intents.
        Args:
            state (IntentState): The current state containing user input.
        Returns:
            IntentState: Updated state with fallback response.
        """
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
        """
        Return node name based on intent.
        Args:
            state (IntentState): The current state containing detected intent.
        Returns:
            str: The next node identifier ("banking", "friendly", or "fallback").
        """
        intent = state["intent"]
        if intent == "customer_request":
            return "banking"
        if intent == "friendly_chat":
            return "friendly"
        if intent in ("general_query", "sql_query"):
            return "fallback"
        return "fallback"

    def _build_graph(self):
        """
        Construct and compile the LangGraph state machine.
        Returns:
            StateGraph: The constructed state graph.
        """
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
        """
        Run the graph for the given state.
        Args:
            state (IntentState): The initial state for the Intent agent.
        Returns:
            IntentState: The final state after processing.
        """
        return self.graph.invoke(state)
