"""
Read-only queries on CHD open data and dossier page facts (#119).
"""
from datetime import datetime

from sqlmodel import Session
from sqlmodel import select

from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.chd_opendata import BallotDossier
from app.db_model.tables.chd_opendata import Deputy
from app.db_model.tables.chd_opendata import OpenDataImport
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
