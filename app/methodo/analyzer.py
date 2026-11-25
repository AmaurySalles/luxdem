"""
Generates a structured policy analysis using a local LLM, cross-referencing:
- Coalition agreement promises (KPI baseline)
- Enacted/in-progress/rejected laws
- ONH empirical research findings
"""
import json
from dataclasses import dataclass
from typing import Any  # the model's JSON

from ecodev_core import logger_get
from ollama import Client
from pydantic import BaseModel

from app.domain_model import LawAssessment
from app.domain_model import OnhStance

from app.methodo.evidence import find_citations, find_overcited_sentences, Passage
from app.methodo.local_llm import chat_completion
from app.methodo.reranker import RankedLaw, RankedOnh

log = logger_get(__name__)


class CitedVerdict(BaseModel):
    """A verdict on coalition commitments, with the passages it saw and its citation checks."""
    coalition_commitments: list[str]
    analysis_text: str
    gaps_identified: list[str]
    conclusion: str
    # Verbatim passages the verdict saw, and citation checks (#101). Defaults keep stored
    # pre-#101 results loadable.
    passages: list[Passage] = []
    unknown_citations: list[str] = []
    uncited_items: list[str] = []
    overcited_sentences: list[str] = []


class TopicAnalysisResult(CitedVerdict):
    topic: str
    matched_laws: list[RankedLaw]
    matched_onh_reports: list[RankedOnh]


@dataclass(frozen=True)
class LawUnderReview:
    number: str
    title: str
    status: str
    summary: str


class OnhFinding(BaseModel):
    finding: str  # an ONH finding or recommendation, with its citation
    stance: OnhStance | None = None  # None: the model gave none of the three


class LawVerdict(CitedVerdict):
    """
    One law against the coalition agreement and against ONH research (demo of 2026-11-27).

    Defaults keep verdicts stored before the ONH leg (prompt version 2) loadable.
    """
    dossier_number: str
    assessment: LawAssessment | None = None  # None: the model gave none of the three
    onh_findings: list[OnhFinding] = []
    onh_conclusion: str = ""


@dataclass(frozen=True)
class VerdictEvidence:
    """Passages per source: coalition excerpts, laws by dossier number, ONH reports by id."""
    coalition: list[Passage]
    laws: dict[str, list[Passage]]
    onh: dict[int, list[Passage]]

    def all_passages(self) -> list[Passage]:
        return [*self.coalition, *(p for ps in self.laws.values() for p in ps),
                *(p for ps in self.onh.values() for p in ps)]


_SOURCE_RULES = """Every excerpt and passage starts with an id in square brackets, e.g. [dossier/8589#42].
Citation rules:
- Base every claim on the verbatim passages, not on the summaries.
- End every sentence that makes a claim with the ids of the passages that support it,
  e.g. "... [dossier/8589#42; onh/note-38.pdf#3]".
- Cite at most 3 ids per sentence: only passages that state the claim itself, not passages
  on the same subject or a bill's title.
- Only cite ids you were given. If no passage supports a claim, leave the claim out.

Write every field in French, whatever the language of the sources.

Text wrapped in ~~double tildes~~ is struck through in the source: wording a bill deletes.
Read the unmarked text as the current version."""

_JSON_FIELDS = """Return ONLY a valid JSON object with these exact fields:
{
  "coalition_commitments": ["commitment 1 [coalition#...]", ...],
  "analysis_text": "multi-paragraph prose analysis, each paragraph ending with its citations",
  "gaps_identified": ["gap 1 [ids]", ...],
  "conclusion": "2-3 sentence judgment on track/partially/failing"
}"""

_ANALYSIS_SYSTEM_PROMPT = f"""You are an expert in Luxembourg housing policy and legislative analysis.
You will receive:
1. A topic/issue to analyze
2. Excerpts from the coalition agreement 2023-2028 (government promises / KPIs)
3. Relevant laws and legislative proposals (with their status: enacted, in progress, or rejected):
   a summary for orientation, then verbatim passages
4. ONH (Observatoire National de l'Habitat) research reports: a summary, then verbatim passages

{_SOURCE_RULES}

Your task: assess whether the government's legislative response is delivering on its coalition commitments for this topic.

- For enacted laws: assess actual impact based on ONH data
- For laws in progress: note them as pending intent
- For rejected/withdrawn laws: treat as failed attempts and flag the gap

{_JSON_FIELDS}"""

# Bumped with each change to the per-law prompt, so stored verdicts are regenerated
LAW_VERDICT_PROMPT_VERSION = 4
_DOSSIER_SYSTEM_PROMPT = f"""You are an expert in Luxembourg housing policy and
legislative analysis.
You will receive:
1. One law or legislative proposal, with its status: a summary for orientation, then verbatim
   passages
2. Excerpts from the coalition agreement 2023-2028 (government promises / KPIs)
3. ONH (Observatoire National de l'Habitat) research reports: verbatim passages with their
   findings and recommendations

{_SOURCE_RULES}

Your task has two parts.

Part 1: assess which coalition commitments this law delivers on, how far, and what those
commitments still need that this law leaves out.

- List only the commitments this law acts on; if it acts on none of the excerpts, say so.
- For an enacted law: assess its impact against ONH data
- For a law in progress: treat it as pending intent
- Call the coalition agreement "l'accord de coalition 2023-2028"; write no English words.

Choose one assessment, by these definitions:
- "{LawAssessment.Delivers.value}": the law does what the commitments it acts on promise.
- "{LawAssessment.Partial.value}": the law acts on a commitment but leaves out a specific part
  of it; name that part as a gap, with the citation of the commitment.
- "{LawAssessment.Unrelated.value}": the law acts on none of the commitments given.
A law that does what it set out to do is not partial because other commitments remain open.

Part 2: compare the law with the ONH research. List each constat or recommendation of the ONH
passages that bears on what this law does, with its citation. Only these count:
- a constat: a measured result, figure or observed trend (prices, shortages, who is excluded,
  how an aid is used);
- a recommendation: what the ONH says should be done.
Never list a description of a law, a policy, its history, a survey or its method: that is
context, not a constat. If no constat or recommendation bears on the law, return an empty list.
For each, say whether the law:
- "{OnhStance.Follows.value}": acts in the direction it points to;
- "{OnhStance.Contradicts.value}": acts against it;
- "{OnhStance.NotAddressed.value}": leaves aside a recommendation on the law's own subject
  (use it for recommendations only, never for a plain constat).
Write « constat », never "finding".

Return ONLY a valid JSON object with these exact fields:
{{
  "assessment": "one of the three assessments above",
  "coalition_commitments": ["commitment 1 [coalition#...]", ...],
  "analysis_text": "multi-paragraph prose analysis, each paragraph ending with its citations",
  "gaps_identified": ["gap 1 [ids]", ...],
  "conclusion": "2-3 sentence judgment explaining the assessment",
  "onh_findings": [{{"finding": "constat or recommendation [onh/...#...]",
                     "stance": "one of the three stances above"}}, ...],
  "onh_conclusion": "1-2 sentences: does the law follow the ONH research, and where not"
}}"""


def generate_analysis(
    client: Client,
    topic: str,
    evidence: VerdictEvidence,
    ranked_laws: list[RankedLaw],
    ranked_onh: list[RankedOnh],
) -> TopicAnalysisResult:
    user_msg = _build_analysis_prompt(topic, evidence, ranked_laws, ranked_onh)
    verdict, _ = _generate_cited_verdict(client, _ANALYSIS_SYSTEM_PROMPT, user_msg,
                                         evidence.all_passages(), label=f"'{topic}'")
    return TopicAnalysisResult(topic=topic, matched_laws=ranked_laws,
                               matched_onh_reports=ranked_onh, **verdict.model_dump())


def generate_dossier_verdict(client: Client, law: LawUnderReview, coalition: list[Passage],
                             law_passages: list[Passage], onh: list[Passage]) -> LawVerdict:
    """Verdict on one law against the coalition excerpts closest to it."""
    user_msg = "\n\n".join([
        f"## Law\n### #{law.number} — {law.title}\n**Status**: {law.status}\n\n"
        f"Summary: {law.summary}\n\nPassages:\n{_format_passages(law_passages)}",
        f"## Coalition Agreement 2023–2028 (relevant excerpts)\n{_format_passages(coalition)}",
        f"## ONH Research Reports\n{_format_passages(onh)}",
    ])
    verdict, parsed = _generate_cited_verdict(client, _DOSSIER_SYSTEM_PROMPT, user_msg,
                                              [*coalition, *law_passages, *onh],
                                              label=f"#{law.number}")
    assessments = {a.value: a for a in LawAssessment}
    assessment = assessments.get(parsed.get("assessment", ""))
    if assessment is None:
        log.warning(f"Verdict for #{law.number}: no valid assessment {parsed.get('assessment')!r}")
    findings = _onh_findings(parsed.get("onh_findings", []))
    onh_conclusion = parsed.get("onh_conclusion", "")
    # the ONH leg goes through the same citation checks as the coalition leg
    known = {p.id for p in verdict.passages}
    onh_cited = find_citations("\n".join([*(f.finding for f in findings), onh_conclusion]))
    checks = {
        "unknown_citations": sorted(set(verdict.unknown_citations) | (set(onh_cited) - known)),
        "uncited_items": [*verdict.uncited_items,
                          *(f.finding for f in findings if not find_citations(f.finding))],
        "overcited_sentences": [
            *verdict.overcited_sentences,
            *(s for f in findings for s in find_overcited_sentences(f.finding))],
    }
    return LawVerdict(dossier_number=law.number, assessment=assessment, onh_findings=findings,
                      onh_conclusion=onh_conclusion, **(verdict.model_dump() | checks))


def _onh_findings(raw: list[Any]) -> list[OnhFinding]:
    """Findings from the model's JSON; malformed entries are dropped and logged."""
    stances = {s.value: s for s in OnhStance}
    findings = []
    for item in raw:
        if not (isinstance(item, dict) and isinstance(item.get("finding"), str)):
            log.warning(f"Malformed ONH finding dropped: {item!r}")
            continue
        findings.append(OnhFinding(finding=item["finding"], stance=stances.get(item.get("stance"))))
    return findings


def _generate_cited_verdict(client: Client, system_prompt: str, user_msg: str,
                            passages: list[Passage], label: str,
                            ) -> tuple[CitedVerdict, dict[str, Any]]:
    """The verdict with its citation checks, and the model's raw JSON for mode-specific fields."""
    raw = chat_completion(client, system_prompt, user_msg, json_mode=True)
    parsed = _parse_analysis_json(raw)
    if not parsed.get("analysis_text"):
        # gemma3:12b returned an empty verdict once in 3 (#103 round 1); sampling may differ
        log.warning(f"Empty verdict for {label}, retrying once")
        raw = chat_completion(client, system_prompt, user_msg, json_mode=True)
        parsed = _parse_analysis_json(raw)
    commitments = parsed.get("coalition_commitments", [])
    analysis_text = parsed.get("analysis_text", raw)
    gaps = parsed.get("gaps_identified", [])
    conclusion = parsed.get("conclusion", "")

    known = {p.id for p in passages}
    cited = find_citations("\n".join([*commitments, analysis_text, *gaps, conclusion]))
    paragraphs = [p for p in analysis_text.split("\n\n") if p.strip()]
    result = CitedVerdict(
        coalition_commitments=commitments,
        analysis_text=analysis_text,
        gaps_identified=gaps,
        conclusion=conclusion,
        passages=passages,
        unknown_citations=sorted(set(cited) - known),
        uncited_items=[item for item in [*commitments, *paragraphs, *gaps]
                       if not find_citations(item)],
        overcited_sentences=[sentence for item in [*commitments, *paragraphs, *gaps, conclusion]
                             for sentence in find_overcited_sentences(item)],
    )
    if result.unknown_citations or result.uncited_items or result.overcited_sentences:
        log.warning(f"Verdict for {label}: {len(result.unknown_citations)} unknown citations, "
                    f"{len(result.uncited_items)} uncited items, "
                    f"{len(result.overcited_sentences)} sentences citing over 3 ids")
    return result, parsed


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
