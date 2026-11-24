"""
Per-law verdicts (demo of 2026-11-27): which coalition commitments each law delivers on.

The law's own summary is the search query: it picks the coalition excerpts and ONH passages
the verdict weighs, so every law gets a verdict, unlike the topic pipeline's top 5.
"""
from ecodev_core import logger_get
from sqlmodel import Session

from app.db_model.retrievers.dossier_retriever import persist_dossier_verdict
from app.db_model.retrievers.dossier_retriever import retrieve_dossier_verdict
from app.db_model.tables.dossier import Dossier
from app.methodo.analyzer import generate_dossier_verdict
from app.methodo.analyzer import LAW_VERDICT_PROMPT_VERSION
from app.methodo.analyzer import LawUnderReview
from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.evidence import DocType
from app.methodo.evidence import retrieve_documents
from app.methodo.evidence import retrieve_dossier_passages
from app.methodo.evidence import retrieve_passages
from app.methodo.evidence import SUMMARY_FOCUS_QUERY
from app.methodo.local_llm import CHAT_MODEL_ID
from app.methodo.local_llm import get_local_llm_client
from app.methodo.main_pipeline import OLLAMA_EMBEDDING_MODEL
from app.methodo.summarizer import get_or_generate_law_summary

log = logger_get(__name__)

K_LAW_PASSAGES = 8
K_COALITION = 6
N_ONH_REPORTS = 2
# Stored as the verdict's model_used: a new model or a new prompt regenerates it
VERDICT_VERSION = f"{CHAT_MODEL_ID}/law-prompt-{LAW_VERDICT_PROMPT_VERSION}"


def dossier_verdict_pipeline(session: Session, dossiers: list[Dossier]) -> None:
    """Verdict for each dossier lacking one from the pinned chat model, stored in the DB."""
    client = get_local_llm_client()
    vectorstore = get_create_chroma_vectorstore(model=OLLAMA_EMBEDDING_MODEL)
    for dossier in dossiers:
        cached = retrieve_dossier_verdict(session, dossier.id)
        if cached and cached.model_used == VERDICT_VERSION:
            log.info(f"Using cached verdict for dossier #{dossier.number}")
            continue
        log.info(f"Generating verdict for dossier #{dossier.number}")
        summary = get_or_generate_law_summary(session, vectorstore, client, dossier)
        law = LawUnderReview(number=dossier.number, title=dossier.title, summary=summary,
                             status=dossier.status.value if dossier.status else "Unknown")
        onh_docs = retrieve_documents(vectorstore, summary, DocType.ONH, N_ONH_REPORTS)
        verdict = generate_dossier_verdict(
            client, law,
            coalition=retrieve_passages(vectorstore, summary, DocType.COALITION, K_COALITION),
            law_passages=retrieve_dossier_passages(vectorstore, SUMMARY_FOCUS_QUERY,
                                                   dossier.number, K_LAW_PASSAGES),
            onh=[passage for doc in onh_docs for passage in doc.passages],
        )
        persist_dossier_verdict(session, dossier.id, verdict.model_dump_json(), VERDICT_VERSION)
