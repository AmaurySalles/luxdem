"""
Pipeline to download, parse, and embed ONH publications into Chroma.
"""
import hashlib
from pathlib import Path

from ecodev_core import logger_get
from langchain_chroma import Chroma
from sqlmodel import Session

from app.db_model.retrievers.onh_retriever import retrieve_onh_publications
from app.db_model.tables.onh_publication import OnhPublication
from app.methodo.chroma import embed_and_store_in_chroma, get_create_chroma_vectorstore
from app.methodo.main_pipeline import OLLAMA_EMBEDDING_MODEL
from app.methodo.onh_paths import DOWNLOADS_DIR
from app.methodo.onh_paths import resolve_onh_source
from app.methodo.parse_cache import load_cached_chunks
from app.methodo.parse_cache import PARSE_CACHE_DIR
from app.methodo.parse_cache import ParseJob
from app.methodo.parse_cache import save_cached_chunks
from app.methodo.parsing.docling_parser import parse_with_docling

log = logger_get(__name__)

# logement-en-chiffre stat-infographic pages produce isolated chunks of raw
# numbers/labels with no sentence structure (~40 words); every prose chunk
# across sampled ONH reports runs 60+ words, so this threshold drops the
# unattributable infographic/front-matter noise while keeping all narrative
# content (see issue #12).
ONH_MIN_CHUNK_WORDS = 50

COALITION_PDF = DOWNLOADS_DIR / "accord_coalition_2023_2028.pdf"
COALITION_CACHE_KEY = "coalition:accord_coalition_2023_2028"


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
        source = resolve_onh_source(pub.url)
        first_id = hashlib.md5(f"{pub.url}::0".encode()).hexdigest()
        if vectorstore.get(ids=[first_id])["ids"]:
            log.info(f"Already embedded, skipping: {pub.title}")
            continue

        log.info(f"Processing ONH publication: {pub.title}")
        metadata = _get_onh_metadata(pub)
        try:
            chunks = parse_with_docling(source, metadata, min_chunk_words=ONH_MIN_CHUNK_WORDS)
            log.info(f"   → {len(chunks)} chunks")
            embed_and_store_in_chroma(chunks, vectorstore)
        except Exception as e:
            log.error(f"Failed to process {pub.title}: {e}")


def coalition_parse_job(pdf_path: Path) -> ParseJob:
    """
    The coalition agreement as a parse job.

    Purpose: parsed on the parse box from the manifest (#71), then read from the parse
    cache by `coalition_agreement_pipeline`.

    NOTE: `COALITION_CACHE_KEY` only keys the cache entry. It is not put in the chunk
    metadata, so the coalition's Chroma chunk ids stay as they were.
    """
    metadata = {
        "doc_type": "coalition",
        "source": "accord_coalition_2023_2028",
        "title": "Accord de coalition 2023-2028",
    }
    # skip the cover page + table of contents (page 3 is where chapters start)
    return ParseJob(source_url=COALITION_CACHE_KEY, label="coalition agreement",
                    source=str(pdf_path), metadata=metadata, content_start_page=3)


def coalition_agreement_pipeline(pdf_path: Path,
                                 cache_dir: Path = PARSE_CACHE_DIR,
                                 embedding_model: str = OLLAMA_EMBEDDING_MODEL) -> None:
    """Embed the coalition agreement PDF into Chroma, parsing it only if not cached."""
    log.info(f"Ingesting coalition agreement: {pdf_path}")
    job = coalition_parse_job(pdf_path)
    fingerprint = job.fingerprint()
    chunks = load_cached_chunks(cache_dir, job.source_url, fingerprint)
    if chunks is None:
        chunks = job.parse()
        save_cached_chunks(cache_dir, job.source_url, job.label, fingerprint, chunks)
    else:
        log.info("   → read from the parse cache")
    log.info(f"   → {len(chunks)} chunks")
    vectorstore = get_create_chroma_vectorstore(model=embedding_model)
    _delete_coalition_chunks(vectorstore)
    embed_and_store_in_chroma(chunks, vectorstore)
    log.info("Coalition agreement embedded successfully.")


def _delete_coalition_chunks(vectorstore: Chroma) -> None:
    """Delete existing doc_type="coalition" chunks before re-ingesting."""
    # chunk ids are index-based (not content-hashed), so re-chunking that shifts
    # chunk_index boundaries would otherwise leave stale chunks behind
    existing = vectorstore.get(where={"doc_type": "coalition"})["ids"]
    if existing:
        log.info(f"   → Deleting {len(existing)} existing coalition chunks")
        vectorstore.delete(ids=existing)


def _get_onh_metadata(pub: OnhPublication) -> dict:
    return {
        "doc_type": "onh",
        "onh_id": pub.id,
        "title": pub.title,
        "category": pub.category or "etude",
        "published_date": str(pub.published_date) if pub.published_date else None,
        "source_url": pub.url,
    }
