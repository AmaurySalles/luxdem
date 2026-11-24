"""
A bill's legislative trail (#119, demo of 2026-11-27): when it was tabled, when the Conseil
d'État gave its opinion, when the commission reported, when the Chambre voted and when the
law was published, from the dated activities on its chd.lu page.
"""
import re
from dataclasses import dataclass
from datetime import date

from app.db_model.tables.dossier_page import DossierActivity
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
    return LegislativeTrail(milestones=milestones, phases=phases, activities=activities)
