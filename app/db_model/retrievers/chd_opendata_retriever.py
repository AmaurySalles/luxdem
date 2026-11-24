"""
Read-only queries on CHD open data and dossier page facts (#119).
"""
from datetime import date
from datetime import datetime

from sqlmodel import or_
from sqlmodel import Session
from sqlmodel import select

from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.chd_opendata import BallotDossier
from app.db_model.tables.chd_opendata import CommissionMembership
from app.db_model.tables.chd_opendata import Deputy
from app.db_model.tables.chd_opendata import OpenDataImport
from app.db_model.tables.chd_opendata import SeatVote
from app.db_model.tables.dossier import Dossier
from app.db_model.tables.dossier_page import DossierActivity
from app.db_model.tables.dossier_page import DossierCommission
from app.db_model.tables.dossier_page import DossierRapporteur
from app.db_model.tables.dossier_page import VoteBulletin


def retrieve_deputies(session: Session) -> list[Deputy]:
    return list(session.exec(select(Deputy)).all())


def retrieve_vote_bulletins(session: Session) -> list[VoteBulletin]:
    return list(session.exec(select(VoteBulletin)).all())


def retrieve_ballots_at(session: Session, held_at: datetime) -> list[Ballot]:
    """
    Ballots held at this second.

    Purpose: find the ballot a vote bulletin describes, by its printed date.
    """
    return list(session.exec(select(Ballot).where(Ballot.held_at == held_at)).all())


def retrieve_ballots_for_dossier(session: Session, dossier_number: str) -> list[Ballot]:
    """Ballots on a dossier (law votes, amendments, motions), oldest first."""
    query = (select(Ballot).join(BallotDossier, BallotDossier.ballot_id == Ballot.id)
             .where(BallotDossier.dossier_number == dossier_number).order_by(Ballot.held_at))
    return list(session.exec(query).all())


def retrieve_dossier_commissions(session: Session, dossier_id: int) -> list[str]:
    query = select(DossierCommission.commission_title).where(
        DossierCommission.dossier_id == dossier_id)
    return list(session.exec(query).all())


def retrieve_dossier_rapporteurs(session: Session, dossier_id: int) -> list[str]:
    query = select(DossierRapporteur.name).where(DossierRapporteur.dossier_id == dossier_id)
    return list(session.exec(query).all())


def retrieve_latest_import(session: Session, dataset: int) -> OpenDataImport | None:
    """The last import of a CHD dataset: its date and source url, shown with the data."""
    query = (select(OpenDataImport).where(OpenDataImport.dataset == str(dataset))
             .order_by(OpenDataImport.imported_at.desc()))
    return session.exec(query).first()


def retrieve_deputy(session: Session, deputy_id: int) -> Deputy | None:
    return session.get(Deputy, deputy_id)


def retrieve_seats_of_deputy(session: Session,
                             deputy_id: int) -> list[tuple[SeatVote, Ballot]]:
    """
    Seats a deputy owns or cast (proxies included), with their ballot, newest first.

    Purpose: a deputy's voting record, whether present, absent with a proxy, or holding one.
    """
    query = (select(SeatVote, Ballot).join(Ballot, Ballot.id == SeatVote.ballot_id)
             .where(or_(SeatVote.on_behalf_of_id == deputy_id,
                        SeatVote.cast_by_id == deputy_id),
                    Ballot.is_ambiguous == False)  # noqa: E712 (SQL expression)
             .order_by(Ballot.held_at.desc()))
    return list(session.exec(query).all())


def retrieve_ballot_dossier_numbers(session: Session,
                                    ballot_ids: list[int]) -> dict[int, list[str]]:
    """Dossier numbers per ballot id."""
    query = select(BallotDossier).where(BallotDossier.ballot_id.in_(ballot_ids))
    numbers: dict[int, list[str]] = {}
    for link in session.exec(query).all():
        numbers.setdefault(link.ballot_id, []).append(link.dossier_number)
    return numbers


def retrieve_dossier_numbers_examined_by(session: Session, commission_prefix: str) -> set[str]:
    """Numbers of the dossiers a commission titled `commission_prefix...` examined."""
    query = (select(Dossier.number)
             .join(DossierCommission, DossierCommission.dossier_id == Dossier.id)
             .where(DossierCommission.commission_title.startswith(commission_prefix)))
    return set(session.exec(query).all())


def retrieve_memberships_of_deputy(session: Session, deputy_id: int,
                                   on: date) -> list[CommissionMembership]:
    """Commission roles a deputy held on `on`."""
    query = select(CommissionMembership).where(
        CommissionMembership.deputy_id == deputy_id, CommissionMembership.role_start <= on,
        or_(CommissionMembership.role_end.is_(None), CommissionMembership.role_end >= on))
    return list(session.exec(query).all())


def retrieve_dossier_activities(session: Session, dossier_id: int) -> list[DossierActivity]:
    """A dossier's procedure steps, oldest first."""
    query = (select(DossierActivity).where(DossierActivity.dossier_id == dossier_id)
             .order_by(DossierActivity.day, DossierActivity.id))
    return list(session.exec(query).all())
