"""
File containing the function to insert a dossier into the database.
"""

from sqlmodel import Session, select
from ecodev_core import engine
from app.db_model.tables.dossier import Dossier
from app.domain_model import DossierType, DossierStatus

def upsert_dossier(session: Session, dossier: Dossier):
    """
    Upserts a dossier into the database.
    If the dossier already exists (by number), it will be skipped.
    Otherwise, it will be inserted.
    """
    existing = session.exec(select(Dossier).where(Dossier.number == str(dossier.number))).first()
    if not existing:
        session.add(dossier)
        session.commit()