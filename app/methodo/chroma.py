# === Step 6: Embed and store in Chroma ===
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.methodo.ollama import get_ollama_embeddings
from pathlib import Path
import requests

# === Configuration ===
VECTOR_DB_DIR = Path("vector_db")
VECTOR_DB_DIR.mkdir(exist_ok=True)


def embed_and_store_in_chroma(chunks: list[dict], vectorstore: Chroma) -> None:
    """Embed chunks and store in Chroma vector database."""
    documents = [
        Document(page_content=chunk["page_content"], metadata=chunk["metadata"])
        for chunk in chunks
    ]
    
    print(f"   → Embedding {len(documents)} chunks with Ollama...")
    vectorstore.add_documents(documents)
    print(f"   → Stored in Chroma: {VECTOR_DB_DIR}")


def get_create_chroma_vectorstore() -> Chroma:
    """Initialize or load Chroma vector store."""
    embeddings = get_ollama_embeddings()
    vectorstore = Chroma(
        persist_directory=str(VECTOR_DB_DIR),
        embedding_function=embeddings,
        collection_name="housing_docs"
    )
    return vectorstore


def query_vectorstore(vectorstore: Chroma, query: str, k: int = 3) -> list[dict]:
    """Query the vector store for similar documents."""
    print(f"\n📚 Querying vector store: '{query}'")
    results = vectorstore.similarity_search(query, k=k)
    
    retrieved_docs = []
    for i, doc in enumerate(results, start=1):
        retrieved_docs.append({
            "rank": i,
            "content": doc.page_content,
            "metadata": doc.metadata
        })
        print(f"\n[Result {i}]")
        print(f"Source: {doc.metadata.get('source_url', 'N/A')}")
        print(f"Content: {doc.page_content[:200]}...")
    
    return retrieved_docs