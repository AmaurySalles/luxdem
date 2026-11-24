"""
Write operations for government members (#119).
"""
from sqlmodel import Session
from sqlmodel import delete

from app.db_model.tables.government import GovernmentMandate
from app.db_model.tables.government import PartyStatement


def replace_government(session: Session, mandates: list[GovernmentMandate],
                       statements: list[PartyStatement]) -> None:
    """Replace all mandates and party statements in one transaction."""
    session.exec(delete(GovernmentMandate))
    session.exec(delete(PartyStatement))
    session.add_all([*mandates, *statements])
    session.commit()
