"""
This is the recoupment of modules where to implement all db insertions.
"""
from app.db_model.inserters.draft_law_inserters import upsert_draft_law


__all__ = [
    'upsert_draft_law',
]
