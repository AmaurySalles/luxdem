"""
File containing the enum for document types found on the
Chambre des Députés (Grand-Duché de Luxembourg) website.
"""

from enum import Enum

class DocType(str, Enum):
    """
    Enum for variousdocument types votes by the Chambre 
    des Députés (Grand-Duché de Luxembourg).
    """
    QUESTION = 'Question Parlementaire'
    DOSSIER = 'Dossier Parlementaire'
    DOSSIER_EU = 'Dossier Européen'
    MOTION = 'Motion et résolution'
    DEBATE = 'Débat'
    PETITION = 'Pétition'
