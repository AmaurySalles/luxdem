"""
Summarizes law and ONH publication content using Claude.
Summaries are cached in the DB; Chroma chunks are used as source material.
"""
import anthropic
from ecodev_core import logger_get
from langchain_chroma import Chroma
from sqlmodel import Session

from app.db_model.retrievers.dossier_retriever import (
    persist_dossier_summary,
    retrieve_dossier_summary,
)
from app.db_model.retrievers.onh_retriever import persist_onh_summary, retrieve_onh_summary
from app.db_model.tables.dossier import Dossier
from app.db_model.tables.onh_publication import OnhPublication
from app.methodo.claude import CLAUDE_MODEL

log = logger_get(__name__)

_LAW_SYSTEM_PROMPT = """You are a legal analyst specializing in Luxembourg housing and social policy legislation.
Summarize the provided law/proposal in 250-350 words. Cover:
1. Main objective and scope
2. Key provisions and measures
3. Target beneficiaries or affected parties
4. Implementation mechanisms
Write in English. Be precise and factual. Do not speculate."""

_ONH_SYSTEM_PROMPT = """You are a housing policy researcher specializing in Luxembourg.
Summarize the provided Observatoire National de l'Habitat (ONH) publication in 250-350 words. Cover:
1. Main findings and key statistics
2. Housing market trends identified
3. Policy recommendations made
4. Time period and data sources referenced
Write in English. Be precise and factual."""


def retrieve_chunks_for_doc(vectorstore: Chroma, where_filter: dict, max_chunks: int = 30) -> list[str]:
    """Fetch all Chroma chunks matching the metadata filter."""
    if len(where_filter) > 1:
        # Chroma's `where` requires exactly one operator key; AND multiple
        # equality filters explicitly via `$and`.
        where_filter = {"$and": [{k: v} for k, v in where_filter.items()]}
    result = vectorstore.get(where=where_filter)
    docs = result.get("documents", [])
    return docs[:max_chunks]


def summarize_law(client: anthropic.Anthropic, dossier_number: str, dossier_title: str, chunks: list[str]) -> str:
    chunks_text = "\n\n---\n\n".join(chunks)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": _LAW_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"Dossier #{dossier_number}: {dossier_title}\n\n{chunks_text}",
        }],
    )
    return response.content[0].text


def summarize_onh_publication(client: anthropic.Anthropic, title: str, chunks: list[str]) -> str:
    chunks_text = "\n\n---\n\n".join(chunks)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": _ONH_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"Publication: {title}\n\n{chunks_text}",
        }],
    )
    return response.content[0].text


def get_or_generate_law_summary(
    session: Session,
    vectorstore: Chroma,
    client: anthropic.Anthropic,
    dossier: Dossier,
) -> str:
    cached = retrieve_dossier_summary(session, dossier.id)
    if cached:
        log.info(f"Using cached summary for dossier #{dossier.number}")
        return cached.summary

    log.info(f"Generating summary for dossier #{dossier.number}")
    chunks = retrieve_chunks_for_doc(vectorstore, {"doc_type": "dossier", "number": dossier.number})
    if not chunks:
        log.warning(f"No Chroma chunks found for dossier #{dossier.number}, using title only")
        chunks = [dossier.title]

    summary = summarize_law(client, dossier.number, dossier.title, chunks)
    persist_dossier_summary(session, dossier.id, summary, CLAUDE_MODEL)
    return summary


def get_or_generate_onh_summary(
    session: Session,
    vectorstore: Chroma,
    client: anthropic.Anthropic,
    publication: OnhPublication,
) -> str:
    cached = retrieve_onh_summary(session, publication.id)
    if cached:
        log.info(f"Using cached summary for ONH publication: {publication.title}")
        return cached.summary

    log.info(f"Generating summary for ONH publication: {publication.title}")
    chunks = retrieve_chunks_for_doc(vectorstore, {"doc_type": "onh", "onh_id": publication.id})
    if not chunks:
        log.warning(f"No Chroma chunks for ONH pub {publication.id}, using title only")
        chunks = [publication.title]

    summary = summarize_onh_publication(client, publication.title, chunks)
    persist_onh_summary(session, publication.id, summary, CLAUDE_MODEL)
    return summary
