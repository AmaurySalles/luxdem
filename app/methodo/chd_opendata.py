"""
Downloads and parses CHD open data from data.public.lu (#119): per-seat plenary votes
(dataset 109) and commission memberships (dataset 104).

Parsing only: `import_chd_opendata` hands the parsed rows to the db_model inserter.
"""
import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from ecodev_core import logger_get
from sqlmodel import Session

from app.db_model.inserters.chd_opendata_inserters import replace_chd_opendata
from app.db_model.inserters.chd_opendata_inserters import upsert_deputies
from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.chd_opendata import BallotDossier
from app.db_model.tables.chd_opendata import CommissionMembership
from app.db_model.tables.chd_opendata import OpenDataImport
from app.db_model.tables.chd_opendata import SeatVote
from app.domain_model.ballot import BallotKind
from app.domain_model.ballot import PoliticalGroupType
from app.domain_model.ballot import VoteChoice
from app.domain_model.ballot import VoteStage

log = logger_get(__name__)

_API = "https://data.public.lu/api/1/datasets"
_TIMEOUT_S = 120
# Dossier numbers run 6000-9999 in the open data period, so a 4-digit year never matches.
_DOSSIER_NUMBER = re.compile(r"(?<!\d)([6-9]\d{3}[AB]?)(?![\dA-Za-z])")
_KIND_BY_PREFIX: list[tuple[re.Pattern, BallotKind]] = [
    (re.compile(r"^(MO|Motion)(?![A-Za-zé])", re.I), BallotKind.Motion),
    (re.compile(r"^(RE|Résolution)(?![A-Za-zé])", re.I), BallotKind.Resolution),
    (re.compile(r"^AM(?![A-Za-z])|amendement", re.I), BallotKind.Amendement),
]
# CHD times are Luxembourg local time; the DB stores aware datetimes.
_CHD_TZ = ZoneInfo("Europe/Luxembourg")
# A deputy holds at most one proxy, so appears at most twice in a real ballot.
_MAX_SEATS_PER_DEPUTY = 2
_SEATS = 60


@dataclass(frozen=True)
class ChdDataset:
    number: int
    slug: str


VOTES = ChdDataset(109, "la-liste-des-votes")
COMMISSIONS = ChdDataset(
    104, "la-liste-differents-organes-commissions-et-delegations-de-la-chambre-des-deputes-du-luxembourg")  # noqa: E501


class OpenDataFormatError(Exception):
    """A CHD open data file no longer has the shape this parser expects."""

    def __init__(self, dataset: ChdDataset, detail: str) -> None:
        super().__init__(f"CHD dataset {dataset.number}: {detail}")
        self.dataset = dataset
        self.detail = detail


@dataclass(frozen=True)
class ParsedSeat:
    last_name: str
    first_name: str
    choice: VoteChoice
    political_group: str
    political_group_type: PoliticalGroupType
    is_own_vote: bool  # deputy listed once: the vote is certainly theirs


@dataclass(frozen=True)
class ParsedBallot:
    label: str
    held_at: datetime
    stage: VoteStage
    kind: BallotKind
    dossier_numbers: list[str]
    is_ambiguous: bool
    seats: list[ParsedSeat]


@dataclass(frozen=True)
class ParsedMembership:
    commission_chd_id: int
    commission_type: str
    commission_title: str
    commission_start: date
    commission_end: date | None
    last_name: str
    first_name: str
    role: str
    role_start: date
    role_end: date | None
    political_group: str


@dataclass(frozen=True)
class DownloadedCsv:
    dataset: ChdDataset
    url: str
    rows: list[dict[str, str]]


def resolve_csv_url(dataset: ChdDataset) -> str:
    """
    URL of the dataset's current CSV resource.

    Purpose: resource URLs change on every CHD refresh, so they are looked up, not pinned.
    """
    response = requests.get(f"{_API}/{dataset.slug}/", timeout=_TIMEOUT_S)
    response.raise_for_status()
    csv_urls = [r["url"] for r in response.json()["resources"] if r["format"].lower() == "csv"]
    if len(csv_urls) != 1:
        raise OpenDataFormatError(dataset, f"expected one CSV resource, found {len(csv_urls)}")
    return csv_urls[0]


def download_csv(dataset: ChdDataset) -> DownloadedCsv:
    """Rows of the dataset's CSV. CHD exports are cp1252 except some UTF-8 (BOM) files."""
    url = resolve_csv_url(dataset)
    response = requests.get(url, timeout=_TIMEOUT_S)
    response.raise_for_status()
    try:
        text = response.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = response.content.decode("cp1252")
    return DownloadedCsv(dataset, url, list(csv.DictReader(io.StringIO(text))))


def parse_dossier_numbers(label: str) -> list[str]:
    """Dossier numbers named in a ballot label, e.g. 'MO 1 - PLs 8765 & 8766' -> both."""
    return list(dict.fromkeys(_DOSSIER_NUMBER.findall(label)))


def classify_ballot(label: str, dossier_numbers: list[str]) -> BallotKind:
    """Motion / résolution / amendement from the label prefix, else dossier if it names one."""
    for pattern, kind in _KIND_BY_PREFIX:
        if pattern.search(label):
            return kind
    return BallotKind.Dossier if dossier_numbers else BallotKind.Autre


_MISSING = {"", "null"}


def _to_date(value: str) -> date | None:
    return None if value in _MISSING else datetime.fromisoformat(value).date()


def drop_export_copies(seat_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    One copy of a ballot the CHD export repeated whole (e.g. 180 rows: every row 3 times).

    Purpose: tell export duplication from labels that merge distinct ballots, which stay ambiguous.
    """
    copies, remainder = divmod(len(seat_rows), _SEATS)
    counts = Counter(tuple(r.items()) for r in seat_rows)
    if copies < 2 or remainder or any(c % copies for c in counts.values()):
        return seat_rows
    return [dict(row) for row, c in counts.items() for _ in range(c // copies)]


def parse_ballots(rows: list[dict[str, str]]) -> list[ParsedBallot]:
    """
    Group dataset 109 seat rows into ballots.

    NOTE: a deputy listed twice cast a proxy; which seat is their own vote is unknown here,
    so neither is marked as own vote.
    """
    by_ballot: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_ballot.setdefault((row["vote_name"].strip(), row["meeting_date"]), []).append(row)

    ballots = []
    for (label, held_at), all_rows in by_ballot.items():
        seat_rows = drop_export_copies(all_rows)
        seats_per_deputy = Counter((r["lastname"], r["firstname"]) for r in seat_rows)
        is_ambiguous = max(seats_per_deputy.values()) > _MAX_SEATS_PER_DEPUTY
        stages = {r["vote_type"] for r in seat_rows}
        if len(stages) != 1:
            raise OpenDataFormatError(VOTES, f"ballot {label!r} has stages {stages}")
        dossier_numbers = parse_dossier_numbers(label)
        ballots.append(ParsedBallot(
            label=label,
            held_at=datetime.fromisoformat(held_at).replace(tzinfo=_CHD_TZ),
            stage=VoteStage(stages.pop()),
            kind=classify_ballot(label, dossier_numbers),
            dossier_numbers=dossier_numbers,
            is_ambiguous=is_ambiguous,
            seats=[ParsedSeat(
                last_name=r["lastname"],
                first_name=r["firstname"],
                choice=VoteChoice(r["vote_result"]),
                political_group=r["rattachement_abrv"],
                political_group_type=PoliticalGroupType(r["rattachement_type"]),
                is_own_vote=(not is_ambiguous
                             and seats_per_deputy[(r["lastname"], r["firstname"])] == 1),
            ) for r in seat_rows],
        ))
    return ballots


def parse_memberships(rows: list[dict[str, str]]) -> list[ParsedMembership]:
    """Deputies' commission roles from dataset 104; staff and delegations are left out."""
    return [ParsedMembership(
        commission_chd_id=int(r["grp_id"]),
        commission_type=r["grp_type_nom"],
        commission_title=r["grp_titre"],
        commission_start=_to_date(r["grp_date_debut"]),
        commission_end=_to_date(r["grp_date_fin"]),
        last_name=r["pph_nom"],
        first_name=r["pph_prenom"],
        role=r["rol_intitule"],
        role_start=_to_date(r["rol_date_debut"]),
        role_end=_to_date(r["rol_date_fin"]),
        political_group=r["rattachement_abrv"],
    ) for r in rows if r["grp_type_nom"].startswith("Commission") and r["rattachement_abrv"]]


def _to_rows(ballots: list[ParsedBallot],
             memberships: list[ParsedMembership],
             deputy_ids: dict[tuple[str, str], int],
             ) -> tuple[list[Ballot], list[CommissionMembership]]:
    ballot_rows = [Ballot(
        label=b.label, held_at=b.held_at, stage=b.stage, kind=b.kind, is_ambiguous=b.is_ambiguous,
        dossiers=[BallotDossier(dossier_number=n) for n in b.dossier_numbers],
        seats=[SeatVote(
            cast_by_id=deputy_ids[(s.last_name, s.first_name)],
            on_behalf_of_id=deputy_ids[(s.last_name, s.first_name)] if s.is_own_vote else None,
            choice=s.choice,
            political_group=s.political_group,
            political_group_type=s.political_group_type,
        ) for s in b.seats],
    ) for b in ballots]
    membership_rows = [CommissionMembership(
        commission_chd_id=m.commission_chd_id, commission_type=m.commission_type,
        commission_title=m.commission_title, commission_start=m.commission_start,
        commission_end=m.commission_end, deputy_id=deputy_ids[(m.last_name, m.first_name)],
        role=m.role, role_start=m.role_start, role_end=m.role_end,
        political_group=m.political_group,
    ) for m in memberships]
    return ballot_rows, membership_rows


def import_chd_opendata(session: Session) -> tuple[list[ParsedBallot], list[ParsedMembership]]:
    """
    Download, parse and store datasets 109 and 104, replacing the previous import.

    Purpose: `import-chd-opendata` command; CHD refreshes the data about monthly.
    """
    votes = download_csv(VOTES)
    commissions = download_csv(COMMISSIONS)
    ballots = parse_ballots(votes.rows)
    memberships = parse_memberships(commissions.rows)
    names = ({(s.last_name, s.first_name) for b in ballots for s in b.seats}
             | {(m.last_name, m.first_name) for m in memberships})
    ballot_rows, membership_rows = _to_rows(ballots, memberships, upsert_deputies(session, names))
    imports = [OpenDataImport(dataset=str(d.dataset.number), source_url=d.url,
                              row_count=len(d.rows)) for d in (votes, commissions)]
    replace_chd_opendata(session, ballot_rows, membership_rows, imports)
    log.info(f"Imported {len(ballots)} ballots, {len(memberships)} commission memberships")
    return ballots, memberships
