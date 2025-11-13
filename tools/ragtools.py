from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
from typing import List, Dict, Any
import numpy as np
import os

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
connections.connect(
    "default",
    host=MILVUS_HOST,
    port=MILVUS_PORT,
    db_name="Banks_DB"
)

embedder = SentenceTransformer("all-MiniLM-L6-v2")


# --- Tool input schemas ---
class EmbeddingQueryInput(BaseModel):
    query: str = Field(..., description="The user query text to embed into a vector.")


class SimilaritySearchInput(BaseModel):
    embedding: List[float] = Field(..., description="Embedding vector of the query.")
    collection_name: str = Field(..., description="Milvus collection to search (e.g. bank name).")
    top_k: int = Field(5, description="Number of most similar documents to retrieve.")


# --- Define actual tool functions ---
def embedding_query_tool(query: str) -> List[float]:
    """Embed the input text using a transformer model."""
    print(f"[DEBUG] Embedding query: {query[:60]}")
    emb = embedder.encode(query).tolist()
    return emb


def similarity_tool(embedding: List[float], collection_name: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Query Milvus for top-k similar document chunks."""
    print(f"[DEBUG] Searching Milvus collection: {collection_name}")
    collection = Collection(collection_name)
    search_params = {"metric_type": "L2", "params": {"nprobe": 8}}
    results = collection.search(
        data=[embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        output_fields=["text", "source"],
    )
    hits = []
    for r in results[0]:
        hits.append({
            "text": r.entity.get("text", ""),
            "source": r.entity.get("source", ""),
            "score": r.distance,
        })
    print(f"[DEBUG] Retrieved {len(hits)} results")
    return hits


# --- Register tools ---
embedding_query_structured_tool = StructuredTool.from_function(
    func=embedding_query_tool,
    name="embedding_query_tool",
    description="Generate an embedding vector for a given query text.",
    args_schema=EmbeddingQueryInput,
)

similarity_structured_tool = StructuredTool.from_function(
    func=similarity_tool,
    name="similarity_tool",
    description="Compute similarity between a query embedding and Milvus document vectors.",
    args_schema=SimilaritySearchInput,
)


def build_rag_tools() -> List[StructuredTool]:
    """Return both tools for RAG agent."""
    return [embedding_query_structured_tool, similarity_structured_tool]


if __name__ == "__main__":
    tools = build_rag_tools()
    print(tools[0].invoke({"query": "credit card fee"}))
