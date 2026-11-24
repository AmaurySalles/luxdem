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
from app.db_model.tables.dossier_page import DossierActivity
from app.db_model.tables.dossier_page import DossierCommission
from app.db_model.tables.dossier_page import DossierRapporteur
from app.db_model.tables.dossier_page import VoteBulletin

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


def replace_dossier_page_facts(session: Session,
                               dossier_id: int,
                               commissions: list[DossierCommission],
                               rapporteurs: list[DossierRapporteur],
                               bulletins: list[VoteBulletin],
                               activities: list[DossierActivity],
                               ) -> None:
    """Replace one dossier's scraped commissions, rapporteurs, bulletin links and activities."""
    for table in (DossierCommission, DossierRapporteur, VoteBulletin, DossierActivity):
        session.exec(delete(table).where(table.dossier_id == dossier_id))
    session.add_all([*commissions, *rapporteurs, *bulletins, *activities])
    session.commit()


def set_seat_owners(session: Session, owner_by_seat: dict[int, int]) -> None:
    """Record whose vote each seat is (from a vote bulletin), in one transaction."""
    for seat_id, deputy_id in owner_by_seat.items():
        seat = session.get(SeatVote, seat_id)
        seat.on_behalf_of_id = deputy_id
        session.add(seat)
    session.commit()
