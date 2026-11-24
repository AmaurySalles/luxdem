"""
Enums describing plenary ballots, as published in CHD open data dataset 109 (votes).
"""
from enum import Enum


class VoteChoice(str, Enum):
    """One seat's vote in a ballot (CHD `vote_result`)."""
    Oui = "Oui"
    Non = "Non"
    Abstention = "Abstention"
    PasParticipe = "Pas participé"


class VoteStage(str, Enum):
    """Constitutional stage of a ballot (CHD `vote_type`); 2021-2022 rows are `Not Found`."""
    PremierVote = "Premier vote constitutionnel"
    SecondVote = "Second vote constitutionnel"
    Vote = "Voté"
    Inconnu = "Not Found"


class BallotKind(str, Enum):
    """What a ballot decides, read from its free-text CHD label."""
    Dossier = "dossier"
    Amendement = "amendement"
    Motion = "motion"
    Resolution = "résolution"
    Autre = "autre"


class PoliticalGroupType(str, Enum):
    """A groupe politique has at least 4 deputies; smaller parties form a sensibilité."""
    Groupe = "Groupe politique"
    Sensibilite = "Sensibilité politique"
