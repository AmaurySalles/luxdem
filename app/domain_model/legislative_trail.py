from enum import Enum


class TrailStep(str, Enum):
    """Milestones of a bill's procedure, as chd.lu's activity table names them."""
    Deposit = "Dépôt"
    CouncilOpinion = "Avis du Conseil d'État"
    CommissionReport = "Rapport de commission"
    FirstVote = "Vote à la Chambre"
    Publication = "Publication au Mémorial"


class TrailPhase(str, Enum):
    """The time between two consecutive milestones."""
    AwaitingCouncil = "En attente de l'avis du Conseil d'État"
    InCommission = "En commission, après l'avis"
    AwaitingVote = "Du rapport au vote"
    AwaitingPublication = "Du vote à la publication"
