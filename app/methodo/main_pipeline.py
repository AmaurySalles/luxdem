# === Main Pipeline ===
from sqlmodel import Session
from app.methodo import parse_pdf_with_pdfplumber
# from app.methodo.parsing.reducto import parse_pdf_with_reducto
from langchain_chroma import Chroma

from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.chroma import embed_and_store_in_chroma
from app.methodo.chunk import extract_and_chunk_text
from app.db_model.tables.resource import Resource
from app.methodo.download import download_pdf
from app.methodo.json import save_normalized_json
from app.methodo.ollama import verify_ollama_running
from app.db_model.retrievers import retrieve_all_resources

from ecodev_core import engine, logger_get

from app.methodo.parsing.plumber import chunk_text

log = logger_get(__name__)

# === Configuration ===
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBEDDING_MODEL = "mistral"


def pipeline_with_plumber():
    """
    Find all relevant Resources in db, and download them (first step of pipeline).
    """
    with Session(engine) as session:
        documents_depot= retrieve_all_resources(session, title='Document de dépôt')
    
        for item in documents_depot[0:2]:
            print(f"\n[1/6] Downloading PDF: {item.url}")
            pdf_path = download_pdf(item.url)
            print(f"[2/6] Parsing PDF with PDF plumber")
            parsed_str = parse_pdf_with_pdfplumber(pdf_path)
            print(f"[3/6] Create metadata")
            metadata = {"source_url": item.url, "filename": pdf_path.stem}
            print(f"[4/6] Extract text and chunks")
            parsed_chunks = chunk_text(parsed_str, metadata)
            print(f"   → Created {len(parsed_chunks)} chunks")
            print(f"[5/6] Initializing Chroma vector store...")
            vectorstore = get_create_chroma_vectorstore()
            print(f"[6/6] Embedding and storing chunks in Chroma...")
            embed_and_store_in_chroma(parsed_chunks, vectorstore)            


# === Example Usage ===
if __name__ == "__main__":
    if not verify_ollama_running():
        print("\n⚠️  Please start Ollama first: ollama serve")
        print(f"   Then pull the model: ollama pull {OLLAMA_EMBEDDING_MODEL}")
        exit(1)

    # pdf_urls = [
    #     "https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8534/20250522_Depot.pdf",
    # ]

    # for url in pdf_urls:
    #     try:
    #         vectorstore = process_pdf_url_full(url)
    #         print(f"\n✓ Successfully processed and stored in Chroma")

    #         # Test query
    #         query_vectorstore(vectorstore, "Fonds du Logement missions")
    #     except Exception as e:
    #         print(f"\n✗ Error: {e}")
    #         import traceback
    #         traceback.print_exc()