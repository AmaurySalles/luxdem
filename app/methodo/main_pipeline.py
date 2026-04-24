"""
Main Pipeline consisting of creating metadata and resource chunks for each dossier.
By resource, we mean any type of file related to the dossier
"""

from typing import Any
from sqlmodel import Session
from app.methodo.parsing.reducto import parse_with_reducto

from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.chroma import embed_and_store_in_chroma
from app.methodo.parsing.metadata import get_resource_metadata
from app.db_model.retrievers import retrieve_all_resources
from app.db_model.tables.resource import Resource


from ecodev_core import engine, logger_get
from ecodev_core import SETTINGS
from app.constants import EMBEDDINGS_DIR
from app.methodo.parsing.plumber import parse_with_pdfplumber



""""Establish connection to logger and configuration embedding model"""
log = logger_get(__name__)
OLLAMA_EMBEDDING_MODEL = SETTINGS.ollama.embedding_model

"""Implement Main Pipeline"""
def dossier_pipeline(session: Session,
                     embedding_model: str = OLLAMA_EMBEDDING_MODEL, 
                     with_reducto: bool = True, 
                     limit:  int = 5):
    documents_depot= retrieve_all_resources(session, title='Document de dépôt', limit=limit)

    item_cache = set()
    for item in documents_depot:
        if item.url in item_cache:
            continue

        log.info(f"[1/4] Creating metadata for dossier #{item.dossier.number}")
        item_cache.add(item.url)
        metadata = get_resource_metadata(item)
        
        log.info(f"[2/4] Parsing and creating chunks for dossier")
        if with_reducto:
            parsed_chunks = parse_with_reducto(item.url, metadata)
        else:
            parsed_chunks = parse_with_pdfplumber(item.url, metadata)
        
        log.info(f"   → Created {len(parsed_chunks)} chunks")

        log.info(f"[3/4] Initializing Chroma vector store")
        vectorstore = get_create_chroma_vectorstore(model=embedding_model)

        log.info(f"[4/4] Embedding and storing metadata + chunks in Chroma")
        embed_and_store_in_chroma(parsed_chunks, vectorstore)    
        log.info(f"   → Stored in Chroma: {EMBEDDINGS_DIR}")
