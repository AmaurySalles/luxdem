"""
This is the recoupment of modules where to implement all db insertions.
"""
from app.db_model.inserters.dossier_inserters import upsert_dossier
from app.db_model.inserters.onh_inserters import update_onh_publication_urls


__all__ = [
    'upsert_dossier',
    'update_onh_publication_urls',
]
