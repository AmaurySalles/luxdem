"""
Module listing all public method from the db_model modules

Note: Add new tables to the database upon app initialisation by adding them here.
"""
from ecodev_core import AppActivity
from ecodev_core import AppRight
from ecodev_core import AppUser

from app.db_model.tables.chd_opendata import Ballot
from app.db_model.tables.chd_opendata import BallotDossier
from app.db_model.tables.chd_opendata import CommissionMembership
from app.db_model.tables.chd_opendata import Deputy
from app.db_model.tables.chd_opendata import OpenDataImport
from app.db_model.tables.chd_opendata import SeatVote
from app.db_model.tables.dossier import Dossier
from app.db_model.tables.dossier_page import DossierActivity
from app.db_model.tables.dossier_page import DossierCommission
from app.db_model.tables.dossier_page import DossierRapporteur
from app.db_model.tables.dossier_page import VoteBulletin
from app.db_model.tables.dossier_summary import DossierSummary
from app.db_model.tables.dossier_verdict import DossierVerdict
from app.db_model.tables.government import GovernmentMandate
from app.db_model.tables.government import PartyStatement
from app.db_model.tables.onh_publication import OnhPublication
from app.db_model.tables.onh_summary import OnhSummary
from app.db_model.tables.resource import Resource
from app.db_model.tables.topic_analysis_run import TopicAnalysisRun


__all__ = [
    'AppUser',
    'AppRight',
    'AppActivity',
    'Ballot',
    'BallotDossier',
    'CommissionMembership',
    'Deputy',
    'Dossier',
    'DossierActivity',
    'DossierCommission',
    'DossierRapporteur',
    'DossierSummary',
    'DossierVerdict',
    'GovernmentMandate',
    'OnhPublication',
    'OnhSummary',
    'OpenDataImport',
    'PartyStatement',
    'Resource',
    'SeatVote',
    'TopicAnalysisRun',
    'VoteBulletin',
]
