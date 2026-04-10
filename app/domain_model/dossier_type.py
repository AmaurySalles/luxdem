"""
File containing the Enum for various Dossier Parlementaire types.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional
from enum import Enum

class DossierType(str, Enum):
    """
    Enum for various Dossier Parlementaire types.
    """
    ProjetDeLoi = "Projet de loi"
    PropositionDeLoi = "Proposition de loi"
    ProjetDeReglementGrandDucal: str = "Projet de Reglement Grand-Ducal"