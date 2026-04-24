"""
Reranks candidate laws and ONH publications by relevance to a given topic using Claude.
"""
import json

import anthropic
from ecodev_core import logger_get
from pydantic import BaseModel

from app.methodo.claude import CLAUDE_MODEL

log = logger_get(__name__)


class RankedLaw(BaseModel):
    dossier_number: str
    dossier_title: str
    status: str
    summary: str
    relevance_score: float
    relevance_reasoning: str


class RankedOnh(BaseModel):
    onh_id: int
    title: str
    category: str
    summary: str
    relevance_score: float
    relevance_reasoning: str


_RERANK_SYSTEM_PROMPT = """You are a Luxembourg housing policy expert.
You will receive a topic and a list of candidate documents (laws or research publications).
Score each document's relevance to the topic from 0.0 (irrelevant) to 1.0 (highly relevant).
Return ONLY a valid JSON object with a "ranked" array. Each element must have:
- "index": the candidate's original index (integer)
- "relevance_score": float between 0.0 and 1.0
- "relevance_reasoning": one sentence explaining the score
Sort the array by relevance_score descending."""


def rerank_laws(
    client: anthropic.Anthropic,
    topic: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[RankedLaw]:
    if not candidates:
        return []

    candidate_text = "\n\n".join(
        f"[{i}] #{c['dossier_number']} — {c['dossier_title']} (Status: {c['status']})\n{c['summary']}"
        for i, c in enumerate(candidates)
    )
    user_msg = f"Topic: {topic}\n\nCandidates:\n{candidate_text}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": _RERANK_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    ranked_indices = _parse_ranked_json(raw)

    results = []
    for entry in ranked_indices[:top_k]:
        idx = entry["index"]
        c = candidates[idx]
        results.append(RankedLaw(
            dossier_number=c["dossier_number"],
            dossier_title=c["dossier_title"],
            status=c["status"],
            summary=c["summary"],
            relevance_score=entry["relevance_score"],
            relevance_reasoning=entry["relevance_reasoning"],
        ))
    return results


def rerank_onh(
    client: anthropic.Anthropic,
    topic: str,
    candidates: list[dict],
    top_k: int = 3,
) -> list[RankedOnh]:
    if not candidates:
        return []

    candidate_text = "\n\n".join(
        f"[{i}] {c['title']} (Category: {c['category']})\n{c['summary']}"
        for i, c in enumerate(candidates)
    )
    user_msg = f"Topic: {topic}\n\nONH Research Publications:\n{candidate_text}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": _RERANK_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    ranked_indices = _parse_ranked_json(raw)

    results = []
    for entry in ranked_indices[:top_k]:
        idx = entry["index"]
        c = candidates[idx]
        results.append(RankedOnh(
            onh_id=c["onh_id"],
            title=c["title"],
            category=c["category"],
            summary=c["summary"],
            relevance_score=entry["relevance_score"],
            relevance_reasoning=entry["relevance_reasoning"],
        ))
    return results


def _parse_ranked_json(raw: str) -> list[dict]:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        ranked = data.get("ranked", [])
        return sorted(ranked, key=lambda x: x.get("relevance_score", 0), reverse=True)
    except Exception as e:
        log.error(f"Failed to parse reranker response: {e}\nRaw: {raw[:500]}")
        return []
