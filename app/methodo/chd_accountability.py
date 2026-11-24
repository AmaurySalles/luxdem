"""
Runs the #119 steps that go beyond open data: scrape dossier pages for commissions, rapporteurs
and vote bulletins, then attribute proxy seats from those bulletins.
"""
import time
from dataclasses import dataclass
from dataclasses import field

import requests
from ecodev_core import logger_get
from sqlmodel import Session

from app.db_model.inserters.chd_opendata_inserters import replace_dossier_page_facts
from app.db_model.inserters.chd_opendata_inserters import set_seat_owners
from app.db_model.retrievers.chd_opendata_retriever import retrieve_ballots_at
from app.db_model.retrievers.chd_opendata_retriever import retrieve_deputies
from app.db_model.retrievers.chd_opendata_retriever import retrieve_vote_bulletins
from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.dossier import Dossier
from app.db_model.tables.dossier_page import DossierActivity
from app.db_model.tables.dossier_page import DossierCommission
from app.db_model.tables.dossier_page import DossierRapporteur
from app.db_model.tables.dossier_page import VoteBulletin
from app.domain_model.deputy_names import is_same_person
from app.methodo.dossier_page import scrape_dossier_page
from app.methodo.parsing.download import download_pdf
from app.methodo.proxy_resolution import BulletinMismatchError
from app.methodo.proxy_resolution import KnownDeputy
from app.methodo.proxy_resolution import Seat
from app.methodo.proxy_resolution import resolve_seats
from app.methodo.vote_bulletin import BulletinFormatError
from app.methodo.vote_bulletin import read_bulletin

log = logger_get(__name__)

DOSSIER_URL = "https://www.chd.lu/fr/dossier/{number}"
# chd.lu is a public service: one page per second.
_DELAY_S = 1.0


@dataclass
class ProxyReport:
    """Outcome per bulletin URL, so nothing unresolved goes unnoticed."""
    resolved: list[str] = field(default_factory=list)
    seats_attributed: int = 0
    no_ballot: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def _known_deputies(session: Session) -> list[KnownDeputy]:
    return [KnownDeputy(d.id, d.last_name, d.first_name) for d in retrieve_deputies(session)]


def _deputy_id(name: str, deputies: list[KnownDeputy]) -> int | None:
    ids = [d.deputy_id for d in deputies if is_same_person(name, d.last_name, d.first_name)]
    return ids[0] if len(ids) == 1 else None


def scrape_dossier_pages(session: Session, dossiers: list[Dossier]) -> dict[str, str]:
    """
    Store commissions, rapporteurs and bulletin links of each dossier's page.

    Returns:
        Error per dossier number for pages that could not be read.
    """
    deputies = _known_deputies(session)
    failed: dict[str, str] = {}
    for dossier in dossiers:
        try:
            facts = scrape_dossier_page(DOSSIER_URL.format(number=dossier.number))
        except requests.RequestException as error:
            log.warning(f"Dossier {dossier.number}: {error}")
            failed[dossier.number] = str(error)
            continue
        finally:
            time.sleep(_DELAY_S)
        replace_dossier_page_facts(
            session, dossier.id,
            commissions=[DossierCommission(dossier_id=dossier.id, commission_title=t)
                         for t in facts.commission_titles],
            rapporteurs=[DossierRapporteur(dossier_id=dossier.id, name=n,
                                           deputy_id=_deputy_id(n, deputies))
                         for n in facts.rapporteur_names],
            bulletins=[VoteBulletin(dossier_id=dossier.id, url=u) for u in facts.bulletin_urls],
            activities=[DossierActivity(dossier_id=dossier.id, day=a.day,
                                        description=a.description, actor=a.actor)
                        for a in facts.activities],
        )
    return failed


def _described_ballot(ballots_at_same_second: list[Ballot], bulletin_label: str) -> Ballot | None:
    """
    The one ballot a bulletin describes, or None when it cannot be told apart.

    NOTE: bulletins print labels cut short or wrapped ('PL 8421 - Promotion journalisme' for
    '... professionnel'), so the label only separates ballots held at the same second.
    resolve_seats() still rejects a wrong pick whose seats disagree with the bulletin.
    """
    if len(ballots_at_same_second) == 1:
        return ballots_at_same_second[0]
    prefixed = [b for b in ballots_at_same_second if b.label.startswith(bulletin_label)]
    return prefixed[0] if len(prefixed) == 1 else None


def _resolve_bulletin(session: Session, bulletin_url: str, deputies: list[KnownDeputy],
                      report: ProxyReport) -> None:
    bulletin = read_bulletin(download_pdf(bulletin_url))
    ballot = _described_ballot(retrieve_ballots_at(session, bulletin.held_at), bulletin.label)
    if ballot is None:
        report.no_ballot.append(bulletin_url)
        return
    seats = [Seat(s.id, s.cast_by_id, s.choice, s.on_behalf_of_id) for s in ballot.seats]
    owners = resolve_seats(bulletin, seats, deputies)
    unresolved = {s.seat_id for s in seats if s.on_behalf_of_id is None}
    set_seat_owners(session, {seat_id: owners[seat_id] for seat_id in unresolved})
    report.resolved.append(bulletin_url)
    report.seats_attributed += len(unresolved)


def resolve_proxies(session: Session) -> ProxyReport:
    """
    Attribute proxy seats of every ballot that has a vote bulletin.

    Purpose: run after each open data import, which re-creates seats without owners.
    """
    deputies = _known_deputies(session)
    report = ProxyReport()
    for bulletin in retrieve_vote_bulletins(session):
        try:
            _resolve_bulletin(session, bulletin.url, deputies, report)
        except (requests.RequestException, BulletinFormatError, BulletinMismatchError) as error:
            log.warning(f"{bulletin.url}: {error}")
            report.failed[bulletin.url] = str(error)
    return report
