"""
File containing the function to insert a draft law into the database.
"""

from sqlmodel import Session
from ecodev_core import engine
from app.db_model.tables.draft_law import DraftLaw
from app.domain_model import LawStatus
from app.domain_model import LawType

def upsert_draft_law(draft_law: DraftLaw):
    """
    Upserts a draft law into the database.
    If the draft law already exists, it will be updated.
    Otherwise, it will be inserted.
    """
    with Session(engine) as session:
        session.add(
            existing_draft_law.update(**draft_law.model_dump(exclude_unset=True))
            if (existing_draft_law := session.get(DraftLaw, draft_law.id))
            else draft_law
        )
        session.commit()