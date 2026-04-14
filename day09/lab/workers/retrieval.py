"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3


def _get_embedding_fn():
    """
    Trả về embedding function sử dụng Jina API.
    """
    import requests
    def embed(text: str) -> list:
        jina_key = os.getenv("JINA_API_KEY")
        if not jina_key:
            # Fallback to random for debugging if no key (matched to 1024)
            import random
            return [random.random() for _ in range(1024)]
            
        url = "https://api.jina.ai/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {jina_key}"
        }
        data = {
            "model": os.getenv("JINA_EMBEDDING_MODEL", "jina-embeddings-v3"),
            "input": [text],
            "dimensions": 1024
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    
    return embed


def rerank_with_jina(query: str, chunks: list) -> list:
    """
    Rerank chunks sử dụng Jina Reranker API.
    """
    jina_key = os.getenv("JINA_API_KEY")
    if not jina_key or not chunks:
        return chunks
        
    url = "https://api.jina.ai/v1/rerank"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jina_key}"
    }
    
    documents = [c["text"] for c in chunks]
    data = {
        "model": os.getenv("JINA_RERANKER_MODEL", "jina-reranker-v2-base-multilingual"),
        "query": query,
        "top_n": min(len(chunks), DEFAULT_TOP_K),
        "documents": documents
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        results = response.json()["results"]
        
        reranked_chunks = []
        for res in results:
            idx = res["index"]
            chunk = chunks[idx].copy()
            chunk["score"] = res["relevance_score"]
            reranked_chunks.append(chunk)
        return reranked_chunks
    except Exception as e:
        print(f"⚠️  Jina Rerank failed: {e}")
        return chunks[:DEFAULT_TOP_K]


def _get_collection():
    """
    Kết nối ChromaDB collection.
    """
    import chromadb
    client = chromadb.PersistentClient(path=os.getenv("CHROMA_DB_PATH", "./chroma_db"))
    collection_name = os.getenv("CHROMA_COLLECTION", "day09_docs")
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        collection = client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    return collection


def retrieve_dense(query: str, top_k: int = 20) -> list:
    """
    Dense retrieval: embed query -> query ChromaDB.
    """
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        chunks = []
        for i in range(len(results["documents"][0])):
            chunks.append({
                "id": results["ids"][0][i] if "ids" in results and results["ids"] else str(i),
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i].get("source", "unknown"),
                "score": 1 - results["distances"][0][i],
                "metadata": results["metadatas"][0][i],
            })
            
        return chunks

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        return []

def retrieve_sparse(query: str, top_k: int = 20) -> list:
    """
    Sparse retrieval: thuật toán BM25.
    """
    try:
        from rank_bm25 import BM25Okapi
        collection = _get_collection()
        all_data = collection.get()
        if not all_data or not all_data.get("documents"):
            return []
        
        docs = all_data["documents"]
        tokenized_corpus = [doc.lower().split() for doc in docs]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        chunks = []
        for i in top_indices:
            if scores[i] <= 0:
                continue
            chunks.append({
                "id": all_data["ids"][i],
                "text": docs[i],
                "source": all_data["metadatas"][i].get("source", "unknown"),
                "score": scores[i], 
                "metadata": all_data["metadatas"][i],
            })
        return chunks
    except Exception as e:
        print(f"⚠️  BM25 query failed: {e}")
        return []

def retrieve_hybrid(query: str, top_k: int = 5) -> list:
    """
    Kết hợp Dense + Sparse và Rerank.
    """
    # 1. Lấy top 20 Dense
    dense_chunks = retrieve_dense(query, top_k=20)
    
    # 2. Lấy top 20 Sparse (BM25)
    sparse_chunks = retrieve_sparse(query, top_k=20)
    
    # 3. Kết hợp & Loại bỏ trùng lặp
    combined = {}
    for c in dense_chunks + sparse_chunks:
        cid = c.get("id", c["text"])
        if cid not in combined:
            combined[cid] = c
            
    candidate_chunks = list(combined.values())
    if not candidate_chunks:
        return []
        
    # 4. Rerank bằng Jina AI
    reranked = rerank_with_jina(query, candidate_chunks)
    return reranked[:top_k]

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_hybrid(task, top_k=top_k)

        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {str(e)}")

    state.setdefault("worker_io_logs", []).append(worker_io)

    return state



# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
