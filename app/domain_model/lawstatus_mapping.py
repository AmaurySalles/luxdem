from typing import TYPE_CHECKING, Any, Dict, Optional

from app.domain_model.law_status import LawStatus

# Creating a dictionary matching imported strings 
# to desired Enum values (e.g. "Cree" → LawStatus.Cree = "Créé")

INPUT_LAW_STATUS_MAPPING = {
    "Cree": LawStatus.Cree,
    "EnAttenteDispenseSecond": LawStatus.EnAttenteDispenseSecond,
    "EnCommission": LawStatus.EnCommission,
    "EvacueConjointement": LawStatus.EvacueConjointement,
    "Fusionne": LawStatus.Fusionne,
    "Publie": LawStatus.Publie,
    "Retire": LawStatus.Retire,
    "Vide": LawStatus.Vide,
    "VoteAccepte": LawStatus.VoteAccepte,
    "VoteRefuse": LawStatus.VoteRefuse,
}
