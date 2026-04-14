import os
import requests
import chromadb
from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY = os.getenv("JINA_API_KEY")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "day09_docs")

def get_jina_embedding(text):
    url = "https://api.jina.ai/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}"
    }
    data = {
        "model": os.getenv("JINA_EMBEDDING_MODEL", "jina-embeddings-v3"),
        "input": [text],
        "dimensions": 1024
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

def get_chunks(text, max_len=800, overlap=150):
    """
    Sử dụng Jina Segment API hoặc fallback sang Sliding Window Chunking.
    """
    try:
        url = "https://segment.jina.ai/"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JINA_API_KEY}"
        }
        data = {
            "content": text,
            "return_chunks": True,
            "max_chunk_length": max_len,
            "tokenizer": "cl100k_base"
        }
        res = requests.post(url, headers=headers, json=data, timeout=10)
        res.raise_for_status()
        result = res.json()
        if "chunks" in result:
            return result["chunks"]
    except Exception as e:
        print(f"  [!] Jina Segmenter fallback: {e}")
        
    # Fallback Sliding Window
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + max_len, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += max_len - overlap
    return chunks

def reindex():
    if not JINA_API_KEY:
        print("Error: JINA_API_KEY not found in .env")
        return

    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # Bước quan trọng: Xóa sạch collection cũ để reset Dimension về 1024
    print(f"🗑️ Deleting existing collection '{CHROMA_COLLECTION}'...")
    try:
        client.delete_collection(CHROMA_COLLECTION)
        print("✅ Deleted.")
    except Exception as e:
        print(f"ℹ️ Note: {e}")
    
    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    docs_dir = "./data/docs"
    files = os.listdir(docs_dir)
    
    print(f"Indexing {len(files)} files using Jina API (with Chunking)...")
    
    for i, fname in enumerate(files):
        if not fname.endswith(".txt"):
            continue
        
        fpath = os.path.join(docs_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            
        print(f"[{i+1}/{len(files)}] Processing: {fname}...")
        
        # 1. Chunking
        chunks = get_chunks(content)
        print(f"  -> Generated {len(chunks)} chunks.")
        
        # 2. Embedding & Indexing
        for c_idx, chunk_text in enumerate(chunks):
            embedding = get_jina_embedding(chunk_text)
            
            chunk_id = f"{fname}_chunk_{c_idx}"
            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk_text],
                metadatas=[{"source": fname, "chunk_id": chunk_id}]
            )
            print(f"     ✅ Indexed {chunk_id}")

    print("Re-indexing complete.")

if __name__ == "__main__":
    reindex()
