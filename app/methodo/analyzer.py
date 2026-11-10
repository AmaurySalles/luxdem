"""
Generates a structured policy analysis using a local LLM, cross-referencing:
- Coalition agreement promises (KPI baseline)
- Enacted/in-progress/rejected laws
- ONH empirical research findings
"""
import json
from dataclasses import dataclass

from ecodev_core import logger_get
from ollama import Client
from pydantic import BaseModel

from app.methodo.evidence import find_citations, Passage
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
    # Verbatim passages the verdict saw, and citation checks (#101). Defaults keep stored
    # pre-#101 results loadable.
    passages: list[Passage] = []
    unknown_citations: list[str] = []
    uncited_items: list[str] = []


@dataclass(frozen=True)
class VerdictEvidence:
    """Passages per source: coalition excerpts, laws by dossier number, ONH reports by id."""
    coalition: list[Passage]
    laws: dict[str, list[Passage]]
    onh: dict[int, list[Passage]]

    def all_passages(self) -> list[Passage]:
        return [*self.coalition, *(p for ps in self.laws.values() for p in ps),
                *(p for ps in self.onh.values() for p in ps)]


_ANALYSIS_SYSTEM_PROMPT = """You are an expert in Luxembourg housing policy and legislative analysis.
You will receive:
1. A topic/issue to analyze
2. Excerpts from the coalition agreement 2023-2028 (government promises / KPIs)
3. Relevant laws and legislative proposals (with their status: enacted, in progress, or rejected):
   a summary for orientation, then verbatim passages
4. ONH (Observatoire National de l'Habitat) research reports: a summary, then verbatim passages

Every excerpt and passage starts with an id in square brackets, e.g. [dossier/8589#42].
Citation rules:
- Base every claim on the verbatim passages, not on the summaries.
- End every commitment, every gap and every paragraph of the analysis with the ids of the
  passages that support it, e.g. "... [dossier/8589#42; onh/note-38.pdf#3]".
- Only cite ids you were given. If no passage supports a claim, leave the claim out.

Text wrapped in ~~double tildes~~ is struck through in the source: wording a bill deletes.
Read the unmarked text as the current version.

Your task: assess whether the government's legislative response is delivering on its coalition commitments for this topic.

- For enacted laws: assess actual impact based on ONH data
- For laws in progress: note them as pending intent
- For rejected/withdrawn laws: treat as failed attempts and flag the gap

Return ONLY a valid JSON object with these exact fields:
{
  "coalition_commitments": ["commitment 1 [coalition#...]", ...],
  "analysis_text": "multi-paragraph prose analysis, each paragraph ending with its citations",
  "gaps_identified": ["gap 1 [ids]", ...],
  "conclusion": "2-3 sentence judgment on track/partially/failing"
}"""


def generate_analysis(
    client: Client,
    topic: str,
    evidence: VerdictEvidence,
    ranked_laws: list[RankedLaw],
    ranked_onh: list[RankedOnh],
) -> TopicAnalysisResult:
    user_msg = _build_analysis_prompt(topic, evidence, ranked_laws, ranked_onh)

    raw = chat_completion(client, _ANALYSIS_SYSTEM_PROMPT, user_msg, json_mode=True)
    parsed = _parse_analysis_json(raw)
    commitments = parsed.get("coalition_commitments", [])
    analysis_text = parsed.get("analysis_text", raw)
    gaps = parsed.get("gaps_identified", [])
    conclusion = parsed.get("conclusion", "")

    passages = evidence.all_passages()
    known = {p.id for p in passages}
    cited = find_citations("\n".join([*commitments, analysis_text, *gaps, conclusion]))
    paragraphs = [p for p in analysis_text.split("\n\n") if p.strip()]
    result = TopicAnalysisResult(
        topic=topic,
        coalition_commitments=commitments,
        matched_laws=ranked_laws,
        matched_onh_reports=ranked_onh,
        analysis_text=analysis_text,
        gaps_identified=gaps,
        conclusion=conclusion,
        passages=passages,
        unknown_citations=sorted(set(cited) - known),
        uncited_items=[item for item in [*commitments, *paragraphs, *gaps]
                       if not find_citations(item)],
    )
    if result.unknown_citations or result.uncited_items:
        log.warning(f"Verdict for '{topic}': {len(result.unknown_citations)} unknown citations, "
                    f"{len(result.uncited_items)} uncited items")
    return result


def _format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{p.id}] {p.text}" for p in passages)


def _build_analysis_prompt(
    topic: str,
    evidence: VerdictEvidence,
    ranked_laws: list[RankedLaw],
    ranked_onh: list[RankedOnh],
) -> str:
    parts = [f"## Topic\n{topic}\n"]

    if evidence.coalition:
        parts.append("## Coalition Agreement 2023–2028 (relevant excerpts)")
        parts.append(_format_passages(evidence.coalition))

    if ranked_laws:
        parts.append("\n## Laws and Legislative Proposals")
        for law in ranked_laws:
            parts.append(
                f"### #{law.dossier_number} — {law.dossier_title}\n"
                f"**Status**: {law.status} | **Relevance**: {law.relevance_score:.2f}\n\n"
                f"Summary: {law.summary}\n\n"
                f"Passages:\n{_format_passages(evidence.laws.get(law.dossier_number, []))}"
            )

    if ranked_onh:
        parts.append("\n## ONH Research Reports")
        for report in ranked_onh:
            parts.append(
                f"### {report.title} (Category: {report.category})\n"
                f"**Relevance**: {report.relevance_score:.2f}\n\n"
                f"Summary: {report.summary}\n\n"
                f"Passages:\n{_format_passages(evidence.onh.get(report.onh_id, []))}"
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
