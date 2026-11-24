"""
A bill's legislative trail (#119, demo of 2026-11-27): when it was tabled, when the Conseil
d'État gave its opinion, when the commission reported, when the Chambre voted and when the
law was published, from the dated activities on its chd.lu page.
"""
import re
from dataclasses import dataclass
from datetime import date

from app.db_model.tables.dossier_page import DossierActivity
from app.domain_model import BillHolder
from app.domain_model import TrailPhase
from app.domain_model import TrailStep

# First activity matching each pattern; a missing one means the step has not happened yet
_STEP_PATTERNS = {
    TrailStep.Deposit: re.compile(r"^Déposé"),
    TrailStep.CouncilOpinion: re.compile(r"^Avis du Conseil d.[ÉE]tat"),
    TrailStep.CommissionReport: re.compile(r"^Rapport de commission"),
    TrailStep.FirstVote: re.compile(r"^(Premier vote constitutionnel|Vote)\b"),
    TrailStep.Publication: re.compile(r"^Publié au Mémorial"),
}
_PHASES = [  # (phase, from step, to step)
    (TrailPhase.AwaitingCouncil, TrailStep.Deposit, TrailStep.CouncilOpinion),
    (TrailPhase.InCommission, TrailStep.CouncilOpinion, TrailStep.CommissionReport),
    (TrailPhase.AwaitingVote, TrailStep.CommissionReport, TrailStep.FirstVote),
    (TrailPhase.AwaitingPublication, TrailStep.FirstVote, TrailStep.Publication),
]


# Who holds the bill after each event (first matching pattern); other events change nothing.
# Rules from the procedure: the Conseil d'État gives its opinion on the bill and on every
# amendment; after an opinion the Chambre's commission examines; after the vote the Conseil
# d'État decides on the second vote, then the Gouvernement promulgates and publishes.
_HOLDER_AFTER = [
    (re.compile(r"^Déposé"), BillHolder.Council),
    (re.compile(r"^Amendement"), BillHolder.Council),
    (re.compile(r"^Avis (complémentaire )?du Conseil d.[ÉE]tat"), BillHolder.Chamber),
    (re.compile(r"^Rapport de commission"), BillHolder.Chamber),
    (re.compile(r"^(Premier vote constitutionnel|Vote)\b"), BillHolder.Council),
    (re.compile(r"^(Dispense du second vote|Second vote)"), BillHolder.Government),
]
# NOTE: no time before a government amendment is charged to the Gouvernement: chd.lu does not
# record when drafting starts, and the gap to the previous event depends on unrelated opinions.
_END = re.compile(r"^(Publié au Mémorial|Retiré)")

HOLDER_RULES = [
    "Après le dépôt ou un amendement : le Conseil d'État (avis ou avis complémentaire).",
    "Après un avis du Conseil d'État : la Chambre (examen en commission).",
    "Le travail du Gouvernement sur ses amendements n'est pas daté sur chd.lu : il n'est pas "
    "imputé.",
    "Après le rapport : la Chambre (vote en séance plénière).",
    "Après le vote : le Conseil d'État (dispense du second vote), puis le Gouvernement "
    "(promulgation et publication au Mémorial).",
]


@dataclass(frozen=True)
class HolderSpan:
    holder: BillHolder
    start: date
    end: date
    is_open: bool  # still under way: ends today

    @property
    def days(self) -> int:
        return (self.end - self.start).days


def _first_match(rules: list[tuple[re.Pattern, BillHolder]], text: str) -> BillHolder | None:
    return next((holder for pattern, holder in rules if pattern.match(text)), None)


def holder_spans(activities: list[DossierActivity], today: date) -> list[HolderSpan]:
    """Consecutive periods by who held the bill, merged when the holder does not change."""
    spans: list[HolderSpan] = []
    holder, since = None, None
    for activity in activities:
        if holder is not None and activity.day > since:
            spans.append(HolderSpan(holder, since, activity.day, is_open=False))
            since = activity.day
        if _END.match(activity.description):
            holder = None
            break
        if (after := _first_match(_HOLDER_AFTER, activity.description)) is not None:
            holder, since = after, since if holder == after else activity.day
    if holder is not None and since < today:
        spans.append(HolderSpan(holder, since, today, is_open=True))
    merged: list[HolderSpan] = []
    for span in spans:
        if merged and merged[-1].holder == span.holder and merged[-1].end == span.start:
            merged[-1] = HolderSpan(span.holder, merged[-1].start, span.end, span.is_open)
        else:
            merged.append(span)
    return merged


@dataclass(frozen=True)
class PhaseSpan:
    phase: TrailPhase
    start: date
    end: date
    is_open: bool  # still under way: ends today

    @property
    def days(self) -> int:
        return (self.end - self.start).days


@dataclass(frozen=True)
class LegislativeTrail:
    milestones: dict[TrailStep, date]
    phases: list[PhaseSpan]
    holders: list[HolderSpan]
    activities: list[DossierActivity]

    @property
    def total_days(self) -> int | None:
        return sum(p.days for p in self.phases) if self.phases else None


def legislative_trail(activities: list[DossierActivity], today: date) -> LegislativeTrail:
    """
    Milestones and the phases between them; the current phase runs to `today`.

    NOTE: a step chd.lu skipped (no commission report before a vote) ends the trail's
    known phases there rather than guessing.
    """
    milestones = {}
    for step, pattern in _STEP_PATTERNS.items():
        if found := next((a for a in activities if pattern.match(a.description)), None):
            milestones[step] = found.day
    phases = []
    for phase, start_step, end_step in _PHASES:
        if start_step not in milestones:
            break
        start = milestones[start_step]
        if end_step in milestones:
            phases.append(PhaseSpan(phase, start, milestones[end_step], is_open=False))
            continue
        phases.append(PhaseSpan(phase, start, today, is_open=True))
        break
    return LegislativeTrail(milestones=milestones, phases=phases,
                            holders=holder_spans(activities, today), activities=activities)
