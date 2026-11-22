"""
Write operations for CHD open data (#119).
"""
from sqlmodel import Session
from sqlmodel import delete
from sqlmodel import select

from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.chd_opendata import BallotDossier
from app.db_model.tables.chd_opendata import CommissionMembership
from app.db_model.tables.chd_opendata import Deputy
from app.db_model.tables.chd_opendata import OpenDataImport
from app.db_model.tables.chd_opendata import SeatVote

DeputyName = tuple[str, str]  # (last_name, first_name)


def upsert_deputies(session: Session, names: set[DeputyName]) -> dict[DeputyName, int]:
    """
    Deputy id per name, adding unknown names (flushed, not committed).

    Purpose: deputies are kept across imports so their ids stay stable for later links.
    """
    ids = {(d.last_name, d.first_name): d.id for d in session.exec(select(Deputy)).all()}
    new = [Deputy(last_name=last, first_name=first) for last, first in names - ids.keys()]
    session.add_all(new)
    session.flush()
    return ids | {(d.last_name, d.first_name): d.id for d in new}


def replace_chd_opendata(session: Session,
                         ballots: list[Ballot],
                         memberships: list[CommissionMembership],
                         imports: list[OpenDataImport],
                         ) -> None:
    """
    Replace all ballots and commission memberships in one transaction, logging the import.

    Purpose: `import_chd_opendata` mirrors the current CHD files; nothing is merged.
    """
    for table in (SeatVote, BallotDossier, Ballot, CommissionMembership):
        session.exec(delete(table))
    session.add_all([*ballots, *memberships, *imports])
    session.commit()
