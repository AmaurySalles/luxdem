"""
Pipeline to download, parse, and embed ONH publications into Chroma.
"""
from pathlib import Path

from ecodev_core import SETTINGS, logger_get
from sqlmodel import Session

from app.db_model.retrievers.onh_retriever import retrieve_onh_publications
from app.db_model.tables.onh_publication import OntPublication
from app.methodo.chroma import embed_and_store_in_chroma, get_create_chroma_vectorstore
from app.methodo.main_pipeline import OLLAMA_EMBEDDING_MODEL
from app.methodo.parsing.plumber import parse_with_pdfplumber

log = logger_get(__name__)


def onh_pipeline(session: Session,
                 embedding_model: str = OLLAMA_EMBEDDING_MODEL,
                 limit: int | None = None) -> None:
    """Download, parse, and embed all ONH publications that have been scraped."""
    publications = retrieve_onh_publications(session, limit=limit)
    if not publications:
        log.warning("No ONH publications in DB. Run scrape_onh_command first.")
        return

    vectorstore = get_create_chroma_vectorstore(model=embedding_model)

    for pub in publications:
        log.info(f"Processing ONH publication: {pub.title}")
        metadata = _get_onh_metadata(pub)
        try:
            chunks = parse_with_pdfplumber(pub.url, metadata)
            log.info(f"   → {len(chunks)} chunks")
            embed_and_store_in_chroma(chunks, vectorstore)
        except Exception as e:
            log.error(f"Failed to process {pub.title}: {e}")


def coalition_agreement_pipeline(pdf_path: Path,
                                 embedding_model: str = OLLAMA_EMBEDDING_MODEL) -> None:
    """Parse and embed the coalition agreement PDF into Chroma."""
    log.info(f"Ingesting coalition agreement: {pdf_path}")
    metadata = {
        "doc_type": "coalition",
        "source": "accord_coalition_2023_2028",
        "title": "Accord de coalition 2023-2028",
    }
    vectorstore = get_create_chroma_vectorstore(model=embedding_model)
    chunks = parse_with_pdfplumber(str(pdf_path), metadata)
    log.info(f"   → {len(chunks)} chunks")
    embed_and_store_in_chroma(chunks, vectorstore)
    log.info("Coalition agreement embedded successfully.")


def _get_onh_metadata(pub: OntPublication) -> dict:
    return {
        "doc_type": "onh",
        "onh_id": pub.id,
        "title": pub.title,
        "category": pub.category or "etude",
        "published_date": str(pub.published_date) if pub.published_date else None,
        "source_url": pub.url,
    }
