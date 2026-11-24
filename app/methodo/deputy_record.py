"""
A deputy's voting record on housing laws (#119, demo of 2026-11-27): every seat that was
theirs, whether they voted themselves or by proxy, and the proxies they cast for others.
"""
from dataclasses import dataclass
from datetime import date
from datetime import datetime

from sqlmodel import Session

from app.db_model.retrievers.chd_opendata_retriever import retrieve_ballot_dossier_numbers
from app.db_model.retrievers.chd_opendata_retriever import retrieve_deputies
from app.db_model.retrievers.chd_opendata_retriever import retrieve_deputy
from app.db_model.retrievers.chd_opendata_retriever import retrieve_dossier_numbers_examined_by
from app.db_model.retrievers.chd_opendata_retriever import retrieve_memberships_of_deputy
from app.db_model.retrievers.chd_opendata_retriever import retrieve_seats_of_deputy
from app.domain_model import VoteChoice


class UnknownDeputyError(Exception):
    def __init__(self, deputy_id: int) -> None:
        super().__init__(f"No deputy with id {deputy_id}")
        self.deputy_id = deputy_id


@dataclass(frozen=True)
class DeputyVote:
    held_at: datetime
    label: str
    dossier_numbers: list[str]
    choice: VoteChoice
    political_group: str
    cast_by: str | None  # a colleague who cast this deputy's vote by proxy
    cast_for: str | None  # the absent colleague whose vote this deputy cast
    owner_unknown: bool  # a seat this deputy cast whose owner no bulletin resolved


@dataclass(frozen=True)
class DeputyRecord:
    deputy_id: int
    name: str
    political_groups: list[str]  # as recorded on their seats, newest first
    commissions: list[str]  # roles held today: 'Commission du Logement… (Membre)'
    votes: list[DeputyVote]


def deputy_record(session: Session, deputy_id: int, commission_prefix: str) -> DeputyRecord:
    """The deputy's votes on dossiers examined by a commission titled `commission_prefix...`."""
    deputy = retrieve_deputy(session, deputy_id)
    if deputy is None:
        raise UnknownDeputyError(deputy_id)
    names = {d.id: f"{d.first_name} {d.last_name}" for d in retrieve_deputies(session)}
    seats = retrieve_seats_of_deputy(session, deputy_id)
    numbers = retrieve_ballot_dossier_numbers(session, list({ballot.id for _, ballot in seats}))
    in_scope = retrieve_dossier_numbers_examined_by(session, commission_prefix)
    votes = []
    for seat, ballot in seats:
        dossiers = numbers.get(ballot.id, [])
        if not in_scope.intersection(dossiers):
            continue
        owns = seat.on_behalf_of_id == deputy_id
        casts = seat.cast_by_id == deputy_id
        votes.append(DeputyVote(
            held_at=ballot.held_at, label=ballot.label, dossier_numbers=dossiers,
            choice=seat.choice, political_group=seat.political_group,
            cast_by=names[seat.cast_by_id] if owns and not casts else None,
            cast_for=names[seat.on_behalf_of_id] if casts and seat.on_behalf_of_id
            and not owns else None,
            owner_unknown=seat.on_behalf_of_id is None,
        ))
    groups = list(dict.fromkeys(seat.political_group for seat, _ in seats))
    return DeputyRecord(
        deputy_id=deputy_id, name=names[deputy_id], political_groups=groups,
        commissions=[f"{m.commission_title} ({m.role})"
                     for m in retrieve_memberships_of_deputy(session, deputy_id, date.today())],
        votes=votes,
    )
