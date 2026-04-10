from typing import TYPE_CHECKING, Any, Dict, Optional

from app.domain_model.dossier_status import DossierStatus

# Creating a dictionary matching imported strings 
# to desired Enum values (
# e.g. "Cree" → LawStatus.Cree = "Créé")

INPUT_LAW_STATUS_MAPPING = {
    "Cree": DossierStatus.Cree,
    "EnAttenteDispenseSecond": DossierStatus.EnAttenteDispenseSecond,
    "EnCommission": DossierStatus.EnCommission,
    "EvacueConjointement": DossierStatus.EvacueConjointement,
    "Fusionne": DossierStatus.Fusionne,
    "Publie": DossierStatus.Publie,
    "Retire": DossierStatus.Retire,
    "Vide": DossierStatus.Vide,
    "VoteAccepte": DossierStatus.VoteAccepte,
    "VoteRefuse": DossierStatus.VoteRefuse,
}
