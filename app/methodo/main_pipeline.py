# === Main Pipeline ===
from langchain_chroma import Chroma

from app.methodo.chroma import get_or_create_chroma_vectorstore
from app.methodo.chroma import embed_and_store_in_chroma
from app.methodo.chunk import extract_and_chunk_text
from app.methodo.download import download_pdf
from app.methodo.json import save_normalized_json
from app.methodo.ollama import verify_ollama_running

# === Configuration ===
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBEDDING_MODEL = "mistral"


def process_pdf_url_full(pdf_url: str, with_reducto: bool = False) -> Chroma:
    """
    Complete pipeline: Download → Parse with Reducto → Chunk → Embed → Store in Chroma.
    """
    slug = pdf_url.split("/")[-1].replace(".pdf", "")

    print(f"\n[1/6] Downloading PDF: {pdf_url}")
    pdf_path = download_pdf(pdf_url)

    print(f"[2/6] Parsing PDF with Reducto API...")
    if with_reducto:
        parsed_data = parse_pdf_with_reducto(pdf_path)
    else: 
        parsed_data = parse_pdf_with_pdfplumber(pdf_path)

    print(f"[3/6] Saving normalized JSON...")
    json_path = save_normalized_json(parsed_data, pdf_url, slug)

    print(f"[4/6] Extracting and splitting into chunks...")
    metadata = {"source_url": pdf_url, "filename": slug}
    chunks = extract_and_chunk_text(parsed_data, metadata)
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
