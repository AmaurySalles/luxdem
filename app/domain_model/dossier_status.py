from typing import TYPE_CHECKING, Any, Dict, Optional
from enum import Enum

class DossierStatus(str, Enum):
    Vide = "Vide"
    Cree = "Créé" 
    Retire = "Retiré"
    EnCommission = "En Commission"
    # Les travaux en commission se terminent par l’adoption d’un rapport. 
    # Ce dernier contient le texte final du projet ou de la proposition tel 
    # qu’il est présenté et discuté en séance publique.
    EvacueConjointement = "Evacuation conjointe"
    Fusionne = "Fusionné"
    AviseParConferencePreside = "Avisé par Conférence des Présidents"
    # Sur décision de la Conférence des Présidents, 
    # le projet ou la proposition de loi est mis(e) à l’ordre du jour d’une séance publique.
    EnAttenteDispenseSecond = "En attente d'être dispensé du second vote" 
    # En principe, un second vote doit avoir lieu au moins trois mois après le premier, 
    # mais la Chambre demande généralement au Conseil d’État à être dispensée de ce second vote
    VoteAccepte = "Accepté"
    VoteRefuse = "Refusé"
    Publie = "Publié"
    # Quatre jours après sa publication au Journal officiel du Grand-Duché de Luxembourg, 
    # la loi entre en vigueur et devient obligatoire 