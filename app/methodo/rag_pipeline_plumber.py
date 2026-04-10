import json
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

import requests
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


# === Configuration ===
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBEDDING_MODEL = "mistral"

DATA_DIR = Path("data")
DOWNLOADS_DIR = Path("downloads")
VECTOR_DB_DIR = Path("vector_db")

DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)
VECTOR_DB_DIR.mkdir(exist_ok=True)


# === Step 1: Download PDF ===
def download_pdf(pdf_url: str) -> Path:
    """Download PDF from URL and save locally."""
    filename = pdf_url.split("/")[-1]
    dest = DOWNLOADS_DIR / filename
    
    if dest.exists():
        print(f"   → PDF already downloaded: {dest}")
        return
    
    print(f"   → Downloading {filename}...")
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    dest.write_bytes(response.content)
    print(f"   → Saved to {dest}")
 


# === Step 2: Parse PDF with pdfplumber ===
def parse_pdf_with_pdfplumber(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
    full_text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        print(f"   → Extracting text from {num_pages} pages...")
        
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            full_text += f"\n--- Page {i} ---\n{text}\n"
            
            # Extract tables if present
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    full_text += "\n[TABLE]\n"
                    for row in table:
                        full_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
    
    return full_text.strip()


# === Step 3: Normalize and save JSON ===
def save_normalized_json(full_text: str, pdf_url: str, slug: str) -> Path:
    """Save parsed text and metadata to JSON file."""
    metadata = {
        "source_url": pdf_url,
        "filename": slug,
        "parsed_at": datetime.utcnow().isoformat() + "Z",
    }
    
    normalized_data = {
        "metadata": metadata,
        "full_text": full_text,
    }
    
    out_path = DATA_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(normalized_data, ensure_ascii=False, indent=2))
    print(f"   → Saved normalized JSON: {out_path}")
    return out_path


# === Step 4: Split into Chunks ===
def chunk_text(full_text: str, metadata: Dict, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[Dict]:
    """Split text into chunks with metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    text_chunks = splitter.split_text(full_text)

    chunks_with_metadata = [
        {
            "page_content": chunk,
            "metadata": {**metadata, "chunk_index": i, "chunk_count": len(text_chunks)},
        }
        for i, chunk in enumerate(text_chunks)
    ]
    return chunks_with_metadata


# === Step 5: Ollama Embeddings Setup ===
def get_ollama_embeddings():
    """Initialize Ollama embeddings (Mistral model)."""
    embeddings = OllamaEmbeddings(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_EMBEDDING_MODEL,
    )
    return embeddings


def verify_ollama_running() -> bool:
    """Check if Ollama is running and model is available."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        models = response.json().get("models", [])
        model_names = [m["name"].split(":")[0] for m in models]
        if OLLAMA_EMBEDDING_MODEL in model_names:
            print(f"✓ Ollama is running with {OLLAMA_EMBEDDING_MODEL} model available")
            return True
        else:
            print(f"✗ {OLLAMA_EMBEDDING_MODEL} not found. Available: {model_names}")
            return False
    except Exception as e:
        print(f"✗ Ollama not reachable at {OLLAMA_BASE_URL}: {e}")
        return False


# === Step 6: Embed and store in Chroma ===
def embed_and_store_in_chroma(chunks: List[Dict], vectorstore: Chroma) -> None:
    """Embed chunks and store in Chroma vector database."""
    documents = [
        Document(page_content=chunk["page_content"], metadata=chunk["metadata"])
        for chunk in chunks
    ]
    
    print(f"   → Embedding {len(documents)} chunks with Ollama...")
    vectorstore.add_documents(documents)
    print(f"   → Stored in Chroma: {VECTOR_DB_DIR}")


def get_or_create_chroma_vectorstore() -> Chroma:
    """Initialize or load Chroma vector store."""
    embeddings = get_ollama_embeddings()
    vectorstore = Chroma(
        persist_directory=str(VECTOR_DB_DIR),
        embedding_function=embeddings,
        collection_name="housing_docs"
    )
    return vectorstore


def query_vectorstore(vectorstore: Chroma, query: str, k: int = 3) -> List[Dict]:
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


# === Main Pipeline ===
def process_pdf_url_full(pdf_url: str) -> Chroma:
    """
    Complete pipeline: Download → Parse → Chunk → Embed → Store in Chroma.
    """
    slug = pdf_url.split("/")[-1].replace(".pdf", "")

    print(f"\n[1/6] Downloading PDF: {pdf_url}")
    pdf_path = download_pdf(pdf_url)

    print(f"[2/6] Parsing PDF with pdfplumber...")
    full_text = parse_pdf_with_pdfplumber(pdf_path)

    print(f"[3/6] Saving normalized JSON...")
    json_path = save_normalized_json(full_text, pdf_url, slug)

    print(f"[4/6] Splitting into chunks...")
    metadata = {"source_url": pdf_url, "filename": slug}
    chunks = chunk_text(full_text, metadata)
    print(f"   → Created {len(chunks)} chunks")

    print(f"[5/6] Initializing Chroma vector store...")
    vectorstore = get_or_create_chroma_vectorstore()

    print(f"[6/6] Embedding and storing chunks in Chroma...")
    embed_and_store_in_chroma(chunks, vectorstore)

    return vectorstore


# === Example Usage ===
if __name__ == "__main__":
    if not verify_ollama_running():
        print("\n⚠️  Please start Ollama first: ollama serve")
        print(f"   Then pull the model: ollama pull {OLLAMA_EMBEDDING_MODEL}")
        exit(1)

    pdf_urls = [
        "https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8534/20250522_Depot.pdf",
    ]

    for url in pdf_urls:
        try:
            vectorstore = process_pdf_url_full(url)
            print(f"\n✓ Successfully processed and stored in Chroma")

            # Test query
            query_vectorstore(vectorstore, "Fonds du Logement missions")
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
