"""
Orchestrates the full topic analysis pipeline:
1. Semantic search across dossiers, ONH reports, and coalition agreement
2. Summarize each matched document (DB-cached)
3. Rerank by relevance to topic
4. Generate structured analysis via a local LLM
"""
from ecodev_core import logger_get
from sqlmodel import Session

from app.db_model.retrievers.dossier_retriever import retrieve_dossiers_by_numbers
from app.db_model.retrievers.onh_retriever import retrieve_onh_summary
from app.db_model.tables.onh_publication import OnhPublication
from app.methodo.analyzer import TopicAnalysisResult, generate_analysis
from app.methodo.chroma import get_create_chroma_vectorstore, query_vectorstore
from app.methodo.local_llm import get_local_llm_client
from app.methodo.main_pipeline import OLLAMA_EMBEDDING_MODEL
from app.methodo.reranker import rerank_laws, rerank_onh
from app.methodo.summarizer import (
    get_or_generate_law_summary,
    get_or_generate_onh_summary,
    retrieve_chunks_for_doc,
)

log = logger_get(__name__)


def topic_analysis_pipeline(
    topic: str,
    session: Session,
    k_retrieval: int = 10,
    k_laws: int = 5,
    k_onh: int = 3,
    k_coalition: int = 5,
    embedding_model: str = OLLAMA_EMBEDDING_MODEL,
) -> TopicAnalysisResult:
    log.info(f"Starting topic analysis: '{topic}'")
    client = get_local_llm_client()
    vectorstore = get_create_chroma_vectorstore(model=embedding_model)

    # === Step 1: Parallel semantic search across all three doc types ===
    law_results = _query_by_type(vectorstore, topic, "dossier", k=k_retrieval)
    onh_results = _query_by_type(vectorstore, topic, "onh", k=k_retrieval)
    coalition_chunks = _query_coalition(vectorstore, topic, k=k_coalition)

    # === Step 2: Resolve unique dossiers and summarize ===
    dossier_numbers = _deduplicate_metadata(law_results, "number")
    dossiers = retrieve_dossiers_by_numbers(session, dossier_numbers)
    if not dossiers:
        log.warning("No dossiers found for topic — have you run the embedding pipeline?")

    law_candidates = []
    for dossier in dossiers:
        summary = get_or_generate_law_summary(session, vectorstore, client, dossier)
        law_candidates.append({
            "dossier_number": dossier.number,
            "dossier_title": dossier.title,
            "status": dossier.status.value if dossier.status else "Unknown",
            "summary": summary,
        })

    # === Step 3: Resolve unique ONH publications and summarize ===
    onh_ids = _deduplicate_metadata(onh_results, "onh_id")
    onh_candidates = []
    for onh_id in onh_ids:
        pub = session.get(OnhPublication, int(onh_id))
        if pub.ai_summary is None:
            pub.ai_summary = get_or_generate_onh_summary(session, vectorstore, client, pub)
        onh_candidates.append({
            "onh_id": pub.id,
            "title": pub.title,
            "category": pub.category or "etude",
            "summary": pub.ai_summary,
        })

    # === Step 4: Rerank ===
    ranked_laws = rerank_laws(client, topic, law_candidates, top_k=k_laws)
    ranked_onh = rerank_onh(client, topic, onh_candidates, top_k=k_onh)

    # === Step 5: Generate analysis ===
    result = generate_analysis(client, topic, coalition_chunks, ranked_laws, ranked_onh)
    log.info("Analysis complete.")
    return result


def _query_by_type(vectorstore, topic: str, doc_type: str, k: int) -> list[dict]:
    """Query Chroma filtered by doc_type metadata."""
    try:
        from langchain_chroma import Chroma
        results = vectorstore.similarity_search(topic, k=k, filter={"doc_type": doc_type})
        return [{"content": doc.page_content, "metadata": doc.metadata} for doc in results]
    except Exception as e:
        log.warning(f"Vector search failed for {doc_type}: {e}")
        return []


def _query_coalition(vectorstore, topic: str, k: int) -> list[str]:
    """Return raw coalition agreement chunk texts relevant to the topic."""
    try:
        results = vectorstore.similarity_search(topic, k=k, filter={"doc_type": "coalition"})
        return [doc.page_content for doc in results]
    except Exception as e:
        log.warning(f"Coalition vector search failed: {e}")
        return []


def _deduplicate_metadata(results: list[dict], key: str) -> list[str]:
    """Return unique values of metadata[key] preserving first-occurrence order."""
    seen = set()
    unique = []
    for r in results:
        val = str(r.get("metadata", {}).get(key, ""))
        if val and val not in seen:
            seen.add(val)
            unique.append(val)
    return unique
