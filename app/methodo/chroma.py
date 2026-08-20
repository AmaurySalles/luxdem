import hashlib
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.methodo.ollama import get_ollama_embeddings
from pathlib import Path
from app.constants import EMBEDDINGS_DIR

# === Step 3/4: Initializing Chroma vector store ===

def get_create_chroma_vectorstore(model='nomic-embed-text') -> Chroma:
    """Initialize or load Chroma vector store."""
    embeddings = get_ollama_embeddings(model)
    vectorstore = Chroma(
        persist_directory=str(EMBEDDINGS_DIR),
        embedding_function=embeddings,
        collection_name="dossier_docs"
    )
    return vectorstore

# === Step 4/4: Embed and store in Chroma ===

def embed_and_store_in_chroma(chunks: list[dict], vectorstore: Chroma) -> None:
    """Embed chunks and store in Chroma vector database."""
    documents = [
        Document(
            page_content=chunk["page_content"],
            metadata={
                k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                for k, v in chunk["metadata"].items()
                if v is not None
            },
        )
        for chunk in chunks
    ]
    ids = [
        hashlib.md5(f"{chunk['metadata'].get('source_url', '')}::{i}".encode()).hexdigest()
        for i, chunk in enumerate(chunks)
    ]
    print(f"   → Embedding {len(documents)} chunks with Ollama...")
    vectorstore.add_documents(documents, ids=ids)
    print(f"   → Stored in Chroma: {EMBEDDINGS_DIR}")


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

# def query_vectorstore(vectorstore: Chroma, query: str, k: int = 3) -> list[dict]:
#     """Query the vector store for similar documents."""
#     results = vectorstore.similarity_search(query, k=k)
#     return [
#         {"rank": i, "content": doc.page_content, "metadata": doc.metadata}
#         for i, doc in enumerate(results, start=1)
#  ]
