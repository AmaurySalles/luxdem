"""
Main Pipeline consisting of creating metadata and resource chunks for each dossier.
By resource, we mean any type of file related to the dossier
"""

import hashlib

from sqlmodel import Session
from ecodev_core import logger_get, SETTINGS, engine 

from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.chroma import embed_and_store_in_chroma
from app.methodo.parsing.docling_parser import parse_with_docling
from app.methodo.parsing.metadata import get_resource_metadata
from app.db_model.retrievers import retrieve_all_resources
from app.db_model.tables.resource import Resource


from app.constants import EMBEDDINGS_DIR

log = logger_get(__name__)

"""Configuration"""
OLLAMA_EMBEDDING_MODEL = SETTINGS.ollama.embedding_model

"""Implement Main Pipeline"""
def dossier_pipeline(session: Session,
                     embedding_model: str = OLLAMA_EMBEDDING_MODEL,
                     limit: int | None = None):
    documents_depot = retrieve_all_resources(session, title='Document de dépôt', limit=limit)

    vectorstore = get_create_chroma_vectorstore(model=embedding_model)
    seen_urls: set[str] = set()
    for item in documents_depot:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)

        first_id = hashlib.md5(f"{item.url}::0".encode()).hexdigest()
        if vectorstore.get(ids=[first_id])["ids"]:
            log.info(f"Already embedded, skipping: {item.url}")
            continue

        log.info(f"[1/3] Creating metadata for dossier #{item.dossier.number}")
        metadata = get_resource_metadata(item)

        log.info(f"[2/3] Parsing and creating chunks for dossier")
        parsed_chunks = parse_with_docling(item.url, metadata)
        log.info(f"   → Created {len(parsed_chunks)} chunks")

        log.info(f"[3/3] Embedding and storing in Chroma")
        embed_and_store_in_chroma(parsed_chunks, vectorstore)
        log.info(f"   → Stored in Chroma: {EMBEDDINGS_DIR}")
