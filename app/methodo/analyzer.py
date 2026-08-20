"""
Generates a structured policy analysis using a local LLM, cross-referencing:
- Coalition agreement promises (KPI baseline)
- Enacted/in-progress/rejected laws
- ONH empirical research findings
"""
import json

from ecodev_core import logger_get
from ollama import Client
from pydantic import BaseModel

from app.methodo.local_llm import chat_completion
from app.methodo.reranker import RankedLaw, RankedOnh

log = logger_get(__name__)


class TopicAnalysisResult(BaseModel):
    topic: str
    coalition_commitments: list[str]
    matched_laws: list[RankedLaw]
    matched_onh_reports: list[RankedOnh]
    analysis_text: str
    gaps_identified: list[str]
    conclusion: str


_ANALYSIS_SYSTEM_PROMPT = """You are an expert in Luxembourg housing policy and legislative analysis.
You will receive:
1. A topic/issue to analyze
2. Excerpts from the coalition agreement 2023-2028 (government promises / KPIs)
3. Summaries of relevant laws and legislative proposals (with their status: enacted, in progress, or rejected)
4. Summaries of ONH (Observatoire National de l'Habitat) research reports

Your task: assess whether the government's legislative response is delivering on its coalition commitments for this topic.

- For enacted laws: assess actual impact based on ONH data
- For laws in progress: note them as pending intent
- For rejected/withdrawn laws: treat as failed attempts and flag the gap

Return ONLY a valid JSON object with these exact fields:
{
  "coalition_commitments": ["commitment 1", "commitment 2", ...],
  "analysis_text": "multi-paragraph prose analysis...",
  "gaps_identified": ["gap 1", "gap 2", ...],
  "conclusion": "2-3 sentence judgment on track/partially/failing"
}"""


def generate_analysis(
    client: Client,
    topic: str,
    coalition_chunks: list[str],
    ranked_laws: list[RankedLaw],
    ranked_onh: list[RankedOnh],
) -> TopicAnalysisResult:
    user_msg = _build_analysis_prompt(topic, coalition_chunks, ranked_laws, ranked_onh)

    raw = chat_completion(client, _ANALYSIS_SYSTEM_PROMPT, user_msg, json_mode=True)
    parsed = _parse_analysis_json(raw)

    return TopicAnalysisResult(
        topic=topic,
        coalition_commitments=parsed.get("coalition_commitments", []),
        matched_laws=ranked_laws,
        matched_onh_reports=ranked_onh,
        analysis_text=parsed.get("analysis_text", raw),
        gaps_identified=parsed.get("gaps_identified", []),
        conclusion=parsed.get("conclusion", ""),
    )


def _build_analysis_prompt(
    topic: str,
    coalition_chunks: list[str],
    ranked_laws: list[RankedLaw],
    ranked_onh: list[RankedOnh],
) -> str:
    parts = [f"## Topic\n{topic}\n"]

    if coalition_chunks:
        parts.append("## Coalition Agreement 2023–2028 (relevant excerpts)")
        parts.extend(coalition_chunks)

    if ranked_laws:
        parts.append("\n## Laws and Legislative Proposals")
        for law in ranked_laws:
            parts.append(
                f"### #{law.dossier_number} — {law.dossier_title}\n"
                f"**Status**: {law.status} | **Relevance**: {law.relevance_score:.2f}\n\n"
                f"{law.summary}"
            )

    if ranked_onh:
        parts.append("\n## ONH Research Reports")
        for report in ranked_onh:
            parts.append(
                f"### {report.title} (Category: {report.category})\n"
                f"**Relevance**: {report.relevance_score:.2f}\n\n"
                f"{report.summary}"
            )

    return "\n\n".join(parts)


def _parse_analysis_json(raw: str) -> dict:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception as e:
        log.error(f"Failed to parse analysis response: {e}")
        return {}
