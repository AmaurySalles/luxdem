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
from app.db_model.tables.onh_publication import OnhPublication
from app.methodo.analyzer import generate_analysis, TopicAnalysisResult, VerdictEvidence
from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.evidence import DocType, retrieve_documents, retrieve_passages
from app.methodo.local_llm import get_local_llm_client
from app.methodo.main_pipeline import OLLAMA_EMBEDDING_MODEL
from app.methodo.reranker import rerank_laws, rerank_onh
from app.methodo.summarizer import get_or_generate_law_summary, get_or_generate_onh_summary

log = logger_get(__name__)


def topic_analysis_pipeline(
    topic: str,
    session: Session,
    n_candidates: int = 10,
    k_laws: int = 5,
    k_onh: int = 3,
    k_coalition: int = 5,
    embedding_model: str = OLLAMA_EMBEDDING_MODEL,
) -> TopicAnalysisResult:
    log.info(f"Starting topic analysis: '{topic}'")
    client = get_local_llm_client()
    vectorstore = get_create_chroma_vectorstore(model=embedding_model)

    # === Step 1: Search, grouped by document (n_candidates distinct docs per type) ===
    law_docs = retrieve_documents(vectorstore, topic, DocType.DOSSIER, n_candidates)
    onh_docs = retrieve_documents(vectorstore, topic, DocType.ONH, n_candidates)
    evidence = VerdictEvidence(
        coalition=retrieve_passages(vectorstore, topic, DocType.COALITION, k_coalition),
        laws={d.metadata["number"]: d.passages for d in law_docs},
        onh={int(d.metadata["onh_id"]): d.passages for d in onh_docs},
    )

    # === Step 2: Resolve dossiers and summarize ===
    dossiers = retrieve_dossiers_by_numbers(session, list(evidence.laws))
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
    onh_candidates = []
    for onh_id in evidence.onh:
        pub = session.get(OnhPublication, onh_id)
        summary = get_or_generate_onh_summary(session, vectorstore, client, pub)
        onh_candidates.append({
            "onh_id": pub.id,
            "title": pub.title,
            "category": pub.category or "etude",
            "summary": summary,
        })

    # === Step 4: Rerank ===
    ranked_laws = rerank_laws(client, topic, law_candidates, top_k=k_laws)
    ranked_onh = rerank_onh(client, topic, onh_candidates, top_k=k_onh)

    # === Step 5: Generate analysis ===
    result = generate_analysis(client, topic, evidence, ranked_laws, ranked_onh)
    log.info("Analysis complete.")
    return result
