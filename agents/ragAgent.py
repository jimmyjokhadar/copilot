from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from typing import TypedDict, Dict, Any, List
from tools.ragtools import build_rag_tools

class RagState(TypedDict):
    user_input: str
    context: str | None
    result: Dict[str, Any] | None
    intent: str | None
    bank_name: str
    embedding: list | None  


def create_ragging_agent(bank_name: str):
    tools = build_rag_tools()
    model = ChatOllama(model="gpt-oss:latest", temperature=0.3)

    def embedding_step(state: RagState):
        query = state["user_input"]
        emb = tools[0].invoke({"query": query})
        print(f"[DEBUG] Generated embedding with length {len(emb)}")
        return {**state, "embedding": emb}  

    def similarity_step(state: RagState):
        emb = state.get("embedding")
        if emb is None:
            raise ValueError("Missing embedding in state")
        results = tools[1].invoke({
            "embedding": emb,
            "collection_name": bank_name,
        })
        context_text = "\n".join([r["text"] for r in results])
        return {**state, "context": context_text, "retrieved_docs": results}

    def answer_step(state: RagState):
        prompt = f"Use the following context to answer the question.\n\nContext:\n{state.get('context','No context')}\n\nQuestion: {state['user_input']}\n\nAnswer:"
        response = model.invoke(prompt)
        return {**state, "result": {"content": response.content}}

    g = StateGraph(RagState)
    g.add_node("embedding", embedding_step)
    g.add_node("similarity", similarity_step)
    g.add_node("answer", answer_step)
    g.add_edge(START, "embedding")
    g.add_edge("embedding", "similarity")
    g.add_edge("similarity", "answer")
    g.add_edge("answer", END)

    return g.compile()
