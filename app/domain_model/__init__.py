"""
Module listing all public method from the domain_model modules

You should put here all domain models components not meant to inherit from SQLModel: hence non db
models.
"""
from app.domain_model.plotly_theme import PLOTLY_TOOLS
from app.domain_model.doc_type import DocType
from app.domain_model.dossier_status import DossierStatus
from app.domain_model.dossier_type import DossierType

__all__ = [
    'PLOTLY_TOOLS'
    "DocType",
    "DossierStatus",
    "DossierType",
]
