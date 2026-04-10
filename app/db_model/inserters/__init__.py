"""
This is the recoupment of modules where to implement all db insertions.
"""
from app.db_model.inserters.dossier_inserters import upsert_dossier


__all__ = [
    'upsert_dossier',
]
