"""
Module listing all public method from the db_model modules

Note: Add new tables to the database upon app initialisation by adding them here.
"""
from ecodev_core import AppActivity
from ecodev_core import AppRight
from ecodev_core import AppUser

from app.db_model.tables.dossier import Dossier
from app.db_model.tables.dossier_summary import DossierSummary
from app.db_model.tables.onh_publication import OnhPublication
from app.db_model.tables.onh_summary import OnhSummary
from app.db_model.tables.resource import Resource
from app.db_model.tables.topic_analysis_run import TopicAnalysisRun


__all__ = [
    'AppUser',
    'AppRight',
    'AppActivity',
    'Dossier',
    'DossierSummary',
    'OnhPublication',
    'OnhSummary',
    'Resource',
    'TopicAnalysisRun',
]
