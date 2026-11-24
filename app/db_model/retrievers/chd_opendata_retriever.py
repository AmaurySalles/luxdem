"""
Read-only queries on CHD open data and dossier page facts (#119).
"""
from datetime import datetime

from sqlmodel import Session
from sqlmodel import select

from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.chd_opendata import Deputy
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
