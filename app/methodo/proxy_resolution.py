"""
Attributes every seat of a ballot to the deputy whose vote it is, from its vote bulletin (#119).

Open data names who cast each seat; the bulletin names whose vote it was. All-or-nothing per
ballot: any disagreement between the two leaves the ballot unresolved and is reported.
"""
from collections import defaultdict
from dataclasses import dataclass

from app.domain_model.ballot import VoteChoice
from app.domain_model.deputy_names import is_same_person
from app.methodo.vote_bulletin import Bulletin


class BulletinMismatchError(Exception):
    """A bulletin and the open data disagree on a ballot."""

    def __init__(self, label: str, detail: str) -> None:
        super().__init__(f"{label}: {detail}")
        self.label = label
        self.detail = detail


@dataclass(frozen=True)
class Seat:
    seat_id: int
    cast_by_id: int
    choice: VoteChoice
    on_behalf_of_id: int | None


@dataclass(frozen=True)
class KnownDeputy:
    deputy_id: int
    last_name: str
    first_name: str


def match_deputy(name: str, deputies: list[KnownDeputy], label: str) -> int:
    """Id of the one deputy `name` refers to; raises on none or several."""
    ids = [d.deputy_id for d in deputies if is_same_person(name, d.last_name, d.first_name)]
    if len(ids) != 1:
        raise BulletinMismatchError(label, f"{name!r} matches {len(ids)} deputies")
    return ids[0]


def resolve_seats(bulletin: Bulletin, seats: list[Seat], deputies: list[KnownDeputy],
                  ) -> dict[int, int]:
    """
    Deputy id whose vote each seat is, keyed by seat id.

    NOTE: a proxy holder's two seats are told apart by choice; when both votes are the same,
    either assignment is equivalent.

    Raises:
        BulletinMismatchError: a name, choice or seat count does not line up.
    """
    open_seats: dict[int, list[Seat]] = defaultdict(list)
    for seat in seats:
        open_seats[seat.cast_by_id].append(seat)

    owner_by_seat: dict[int, int] = {}
    for entry in bulletin.entries:
        voter_id = match_deputy(entry.deputy_name, deputies, bulletin.label)
        caster_id = (match_deputy(entry.proxy_holder_name, deputies, bulletin.label)
                     if entry.proxy_holder_name else voter_id)
        # an earlier run's owner first: re-runs must not swap a holder's interchangeable seats
        seat = min((s for s in open_seats[caster_id]
                    if s.choice == entry.choice and s.on_behalf_of_id in (voter_id, None)),
                   key=lambda s: s.on_behalf_of_id is None, default=None)
        if seat is None:
            caster = entry.proxy_holder_name or entry.deputy_name
            raise BulletinMismatchError(bulletin.label,
                                        f"no {entry.choice.value} seat cast by {caster}")
        open_seats[caster_id].remove(seat)
        owner_by_seat[seat.seat_id] = voter_id

    # Left over: non-participants, who cast only their own seat.
    for caster_id, rest in open_seats.items():
        if any(s.choice != VoteChoice.PasParticipe for s in rest) or len(rest) > 1:
            raise BulletinMismatchError(bulletin.label,
                                        f"{len(rest)} seats of deputy {caster_id} not in bulletin")
        owner_by_seat |= {s.seat_id: caster_id for s in rest}

    for seat in seats:
        if seat.on_behalf_of_id not in (None, owner_by_seat[seat.seat_id]):
            raise BulletinMismatchError(bulletin.label, f"seat {seat.seat_id} owner disagrees")
    return owner_by_seat
