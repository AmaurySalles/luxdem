"""
Everything the demo pages show about one dossier (#119, demo of 2026-11-27): summary,
per-law verdict, author at the time, examining commission, rapporteurs and every vote with
each deputy's choice and proxies named.
"""
import json
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from datetime import datetime

from sqlmodel import Session

from app.db_model.retrievers.chd_opendata_retriever import retrieve_ballots_for_dossier
from app.db_model.retrievers.chd_opendata_retriever import retrieve_deputies
from app.db_model.retrievers.chd_opendata_retriever import retrieve_dossier_activities
from app.db_model.retrievers.chd_opendata_retriever import retrieve_dossier_commissions
from app.db_model.retrievers.chd_opendata_retriever import retrieve_dossier_rapporteurs
from app.db_model.retrievers.dossier_retriever import retrieve_dossier_verdict
from app.db_model.retrievers.government_retriever import retrieve_commission_group_on
from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.dossier import Dossier
from app.domain_model import BallotKind
from app.domain_model import VoteChoice
from app.domain_model import VoteStage
from app.methodo.analyzer import LawVerdict
from app.methodo.authors import author_profile
from app.methodo.authors import AuthorProfile
from app.methodo.legislative_trail import legislative_trail
from app.methodo.legislative_trail import LegislativeTrail

CHD_DOSSIER_URL = "https://www.chd.lu/fr/dossier/{number}"


@dataclass(frozen=True)
class SeatRecord:
    deputy_id: int
    deputy: str  # whose vote it is; the caster when the bulletin was not resolved
    political_group: str
    choice: VoteChoice
    proxy_holder: str | None  # who cast it for an absent deputy
    owner_known: bool  # False: a proxy seat whose bulletin is unresolved


@dataclass(frozen=True)
class BallotRecord:
    label: str
    held_at: datetime
    stage: VoteStage
    kind: BallotKind
    counts: dict[VoteChoice, int]
    by_group: dict[str, dict[VoteChoice, int]]
    seats: list[SeatRecord]

    @property
    def unresolved_proxies(self) -> int:
        return sum(not seat.owner_known for seat in self.seats)


@dataclass(frozen=True)
class DossierRecord:
    number: str
    title: str
    deposit_date: date | None
    chd_url: str
    summary: str | None
    verdict: LawVerdict | None
    author: AuthorProfile | None
    commissions: list[str]
    rapporteurs: list[str]
    ballots: list[BallotRecord]
    trail: LegislativeTrail


def dossier_record(session: Session, dossier: Dossier) -> DossierRecord:
    stored = retrieve_dossier_verdict(session, dossier.id)
    author = (author_profile(session, dossier.authors, dossier.deposit_date)
              if dossier.authors and dossier.deposit_date else None)
    names = {d.id: (d.last_name, d.first_name) for d in retrieve_deputies(session)}
    return DossierRecord(
        number=dossier.number,
        title=dossier.title,
        deposit_date=dossier.deposit_date,
        chd_url=CHD_DOSSIER_URL.format(number=dossier.number),
        summary=dossier.ai_summary.summary if dossier.ai_summary else None,
        verdict=LawVerdict.model_validate(json.loads(stored.result_json)) if stored else None,
        author=author,
        commissions=retrieve_dossier_commissions(session, dossier.id),
        rapporteurs=retrieve_dossier_rapporteurs(session, dossier.id),
        ballots=[_ballot_record(session, ballot, names)
                 for ballot in retrieve_ballots_for_dossier(session, dossier.number)
                 if not ballot.is_ambiguous],
        trail=legislative_trail(retrieve_dossier_activities(session, dossier.id), date.today()),
    )


def _ballot_record(session: Session, ballot: Ballot,
                   names: dict[int, tuple[str, str]]) -> BallotRecord:
    seats = []
    for seat in ballot.seats:
        caster = names[seat.cast_by_id]
        owner_id = seat.on_behalf_of_id
        if owner_id is None or owner_id == seat.cast_by_id:
            seats.append(SeatRecord(seat.cast_by_id, _full_name(caster), seat.political_group,
                                    seat.choice,
                                    proxy_holder=None, owner_known=owner_id is not None))
            continue
        owner = names[owner_id]
        # the seat row carries the holder's group; the absent deputy's is their own
        group = (retrieve_commission_group_on(session, *owner, ballot.held_at.date())
                 or seat.political_group)
        seats.append(SeatRecord(owner_id, _full_name(owner), group, seat.choice,
                                proxy_holder=_full_name(caster), owner_known=True))
    by_group: dict[str, Counter[VoteChoice]] = defaultdict(Counter)
    for seat in seats:
        by_group[seat.political_group][seat.choice] += 1
    return BallotRecord(
        label=ballot.label, held_at=ballot.held_at, stage=ballot.stage, kind=ballot.kind,
        counts=dict(Counter(seat.choice for seat in seats)),
        by_group={group: dict(counts) for group, counts in sorted(by_group.items())},
        seats=sorted(seats, key=lambda seat: (seat.political_group, seat.deputy)),
    )


def _full_name(name: tuple[str, str]) -> str:
    last, first = name
    return f"{first} {last}"
