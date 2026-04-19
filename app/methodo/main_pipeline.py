# === Main Pipeline ===
from typing import Any
from sqlmodel import Session
from app.methodo.parsing.reducto import parse_with_reducto

from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.chroma import embed_and_store_in_chroma
from app.db_model.tables.resource import Resource
from app.db_model.retrievers import retrieve_all_resources

from ecodev_core import engine, logger_get
from ecodev_core import SETTINGS
from app.constants import EMBEDDINGS_DIR
from app.methodo.parsing.plumber import parse_with_pdfplumber

log = logger_get(__name__)

# === Configuration ===
OLLAMA_EMBEDDING_MODEL = SETTINGS.ollama.embedding_model


def dossier_pipeline(session: Session,
                     embedding_model: str = OLLAMA_EMBEDDING_MODEL, 
                     with_reducto: bool = True, 
                     limit:  int = 5):
    """
    Find all relevant Resources in db, and download them (first step of pipeline).
    """
    documents_depot= retrieve_all_resources(session, title='Document de dépôt', limit=limit)

    item_cache = set()
    for item in documents_depot:
        if item.url in item_cache:
            continue

        log.info(f"Processing dossier #{item.dossier.number}")
        item_cache.add(item.url)
        metadata = get_resource_metadata(item)
        
        if with_reducto:
            parsed_chunks = parse_with_reducto(item.url, metadata)
        else:
            parsed_chunks = parse_with_pdfplumber(item.url, metadata)
        
        log.info(f"   → Created {len(parsed_chunks)} chunks")

        log.info(f"[3/4] Initializing Chroma vector store...")
        vectorstore = get_create_chroma_vectorstore(model=embedding_model)

        log.info(f"[4/4] Embedding and storing chunks in Chroma...")
        embed_and_store_in_chroma(parsed_chunks, vectorstore)    
        log.info(f"   → Stored in Chroma: {EMBEDDINGS_DIR}")



def get_resource_metadata(resource: Resource) -> dict[str, Any]:
    """
    Get the metadata for a resource.
    """
    if resource.dossier is None:
        raise ValueError("Resource has no dossier")
    
    return {
        "doc_type": "dossier",
        "number": resource.dossier.number,
        "title": resource.dossier.title,
        "summary": resource.dossier.content,
        "authors": resource.dossier.authors,
        "deposit_date": str(resource.dossier.deposit_date) if resource.dossier.deposit_date else None,
        "evacuation_date": str(resource.dossier.evacuation_date) if resource.dossier.evacuation_date else None,
        "status": resource.dossier.status.value if resource.dossier.status else None,
        "type": resource.dossier.type,
        "source_url": resource.url,
    }

