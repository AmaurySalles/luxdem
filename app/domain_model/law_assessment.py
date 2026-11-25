from enum import Enum


class LawAssessment(str, Enum):
    """How far one law delivers the coalition commitments it acts on (per-law verdict)."""
    Delivers = "répond"
    Partial = "répond partiellement"
    Unrelated = "sans lien direct"


class OnhStance(str, Enum):
    """How a law relates to one ONH finding or recommendation."""
    Follows = "suit"
    Contradicts = "va à l'encontre"
    NotAddressed = "non traité"
