import hashlib
from typing import Any

import chromadb
from chromadb.errors import InvalidCollectionException
from ecodev_core import logger_get
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.constants import CHROMA_COLLECTION
from app.constants import CHROMA_DIR
from app.methodo.ollama import get_legacy_ollama_embeddings
from app.methodo.ollama import get_ollama_embeddings
from app.methodo.ollama import OLLAMA_EMBEDDING_MODEL

log = logger_get(__name__)

# Docs per add_documents call: langchain-chroma 0.1.4 embeds the whole list, then does one upsert.
ADD_DOCUMENTS_BATCH_SIZE = 256
# Model of the pre-#51 collections, which carry no `embedding_model` metadata.
LEGACY_EMBEDDING_MODEL = "nomic-embed-text"

# === Step 3/4: Initializing Chroma vector store ===


def _existing_collection_metadata(client: chromadb.ClientAPI, name: str) -> dict[str, Any] | None:
    """Metadata of an existing collection ({} if it has none), None if it does not exist."""
    try:
        return dict(client.get_collection(name).metadata or {})
    except (InvalidCollectionException, ValueError):
        return None


def get_create_chroma_vectorstore(model: str = OLLAMA_EMBEDDING_MODEL) -> Chroma:
    """
    Open or create the configured Chroma collection (config `chroma`).
    New collections use cosine and record model, Ollama version and digest. A pre-#51
    collection (no `embedding_model` metadata) keeps the legacy client so vectors never mix.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    existing = _existing_collection_metadata(client, CHROMA_COLLECTION)
    if existing is not None and "embedding_model" not in existing:
        if model.split(":")[0] != LEGACY_EMBEDDING_MODEL:
            raise ValueError(
                f"{CHROMA_COLLECTION} holds {LEGACY_EMBEDDING_MODEL} vectors, not {model}"
            )
        log.warning(f"{CHROMA_DIR}/{CHROMA_COLLECTION} predates #51: using the legacy client")
        return Chroma(
            client=client,
            collection_name=CHROMA_COLLECTION,
            embedding_function=get_legacy_ollama_embeddings(model),
        )

    embeddings = get_ollama_embeddings(model)
    server_info = embeddings.server_info()
    if existing is not None:
        if existing["embedding_model"] != model:
            raise ValueError(
                f"{CHROMA_COLLECTION} was embedded with {existing['embedding_model']}, not {model}"
            )
        for key, value in server_info.items():
            if existing.get(key) != value:
                log.warning(f"{CHROMA_COLLECTION} {key} is {existing.get(key)}, server has {value}")
    # Only applied on creation: chromadb 0.5 get_or_create ignores metadata for an existing one.
    # Default search_ef (10) missed an exact match among near-duplicate chunks in testing (#51).
    metadata = {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:search_ef": 100,
        "embedding_model": model,
        **server_info,
    }
    return Chroma(
        client=client,
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        collection_metadata=metadata,
    )

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
    for i in range(0, len(documents), ADD_DOCUMENTS_BATCH_SIZE):
        vectorstore.add_documents(
            documents[i:i + ADD_DOCUMENTS_BATCH_SIZE],
            ids=ids[i:i + ADD_DOCUMENTS_BATCH_SIZE],
        )
    print(f"   → Stored in Chroma: {CHROMA_DIR}/{CHROMA_COLLECTION}")


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
