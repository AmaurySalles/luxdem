"""
File containing the function to insert a dossier into the database.
"""

from sqlmodel import Session
from ecodev_core import engine
from app.db_model.tables.dossier import Dossier
from app.domain_model import DossierType, DossierStatus

def upsert_dossier(dossier: Dossier):
    """
    Upserts a dossier into the database.
    If the dossier already exists, it will be updated.
    Otherwise, it will be inserted.
    """
    with Session(engine) as session:
        session.add(
            existing_dossier.update(**dossier.model_dump(exclude_unset=True))
            if (existing_dossier := session.get(Dossier, dossier.id))
            else dossier
        )
        session.commit()