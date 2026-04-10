import hashlib
import os

import chromadb
from langchain_chroma import Chroma

from app.methodo.embeddings import get_embedding_function


CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost").strip()
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "housing_docs_voyage_v1").strip()
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))


def get_chroma_client() -> chromadb.HttpClient:
    """Connect to the running Chroma server."""
    return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


def _chunk_id(chunk: dict) -> str:
    metadata = chunk["metadata"]
    raw_key = "|".join(
        [
            str(metadata.get("source_url", "")),
            str(metadata.get("filename", "")),
            str(metadata.get("chunk_index", "")),
            chunk["page_content"],
        ]
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def embed_and_store_in_chroma(chunks: list[dict], vectorstore: Chroma) -> None:
    """Embed chunks in batches and upsert them into Chroma."""
    total_chunks = len(chunks)
    if total_chunks == 0:
        print("   → No chunks to embed.")
        return

    print(f"   → Embedding {total_chunks} chunks with configured provider...")
    for start in range(0, total_chunks, EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectorstore.add_texts(
            texts=[chunk["page_content"] for chunk in batch],
            metadatas=[chunk["metadata"] for chunk in batch],
            ids=[_chunk_id(chunk) for chunk in batch],
        )
        print(
            f"   → Upserted chunks {start + 1}-{start + len(batch)} "
            f"into Chroma collection '{CHROMA_COLLECTION_NAME}'"
        )


def get_create_chroma_vectorstore() -> Chroma:
    """Initialize or load Chroma over HTTP using the configured embeddings."""
    embeddings = get_embedding_function()
    return Chroma(
        client=get_chroma_client(),
        embedding_function=embeddings,
        collection_name=CHROMA_COLLECTION_NAME,
    )


def query_vectorstore(vectorstore: Chroma, query: str, k: int = 3) -> list[dict]:
    """Query the vector store for similar documents."""
    print(f"\n📚 Querying vector store: '{query}'")
    results = vectorstore.similarity_search(query, k=k)

    retrieved_docs = []
    for i, doc in enumerate(results, start=1):
        retrieved_docs.append(
            {
                "rank": i,
                "content": doc.page_content,
                "metadata": doc.metadata,
            }
        )
        print(f"\n[Result {i}]")
        print(f"Source: {doc.metadata.get('source_url', 'N/A')}")
        print(f"Content: {doc.page_content[:200]}...")

    return retrieved_docs
