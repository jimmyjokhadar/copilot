from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from typing import TypedDict, Dict, Any, List
from tools.ragtools import build_rag_tools
from prompts.ragging_prompt import ragging_prompt
import logging 

logger = logging.getLogger(__name__)

class RagState(TypedDict):
    user_input: str
    context: str | None
    result: Dict[str, Any] | None
    intent: str | None
    bank_name: str
    embedding: list | None


class RagAgent:
    def __init__(self, bank_name: str):
        """Initialize RAG agent with tools and model."""
        self.bank_name = bank_name
        self.tools = build_rag_tools()
        self.model = ChatOllama(model="gpt-oss:latest", temperature=0.3)
        self.graph = self._build_graph()

    def _embedding_step(self, state: RagState) -> RagState:
        """Generate embedding for user query."""
        emb = self.tools[0].invoke({"query": state["user_input"]})
        logger.debug(f"Generated embedding: {emb}")
        return {**state, "embedding": emb}

    def _similarity_step(self, state: RagState) -> RagState:
        """Perform similarity search using embedding."""
        emb = state.get("embedding")
        results = self.tools[1].invoke({
            "embedding": emb,
            "collection_name": self.bank_name
        })
        context_text = "\n".join([r["text"] for r in results])
        logger.debug(f"Retrieved context: {context_text}")
        return {**state, "context": context_text, "retrieved_docs": results}

    def _answer_step(self, state: RagState) -> RagState:
        """Generate final answer using retrieved context."""
        prompt = ragging_prompt(
            state["user_input"],
            state.get("context", "No context")
        )
        response = self.model.invoke(prompt)
        logger.debug(f"Generated answer: {response.content}")
        return {**state, "result": {"content": response.content}}

    def _build_graph(self):
        """Build and compile the RAG state graph."""
        g = StateGraph(RagState)
        g.add_node("embedding", self._embedding_step)
        g.add_node("similarity", self._similarity_step)
        g.add_node("answer", self._answer_step)
        g.add_edge(START, "embedding")
        g.add_edge("embedding", "similarity")
        g.add_edge("similarity", "answer")
        g.add_edge("answer", END)
        return g.compile()

    def invoke(self, state: RagState):
        """Run the state machine for the given RAG state."""
        return self.graph.invoke(state)


def create_ragging_agent(bank_name: str):
    """Factory to create a RagAgent."""
    return RagAgent(bank_name)
