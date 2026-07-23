"""
This is the recoupment of modules where to implement all db retrievals.
"""
from app.db_model.retrievers.dossier_retriever import (
    persist_dossier_summary,
    retrieve_dossier_summary,
    retrieve_dossiers_by_numbers,
)
from app.db_model.retrievers.onh_retriever import (
    persist_onh_summary,
    retrieve_onh_publications,
    retrieve_onh_summary,
    upsert_onh_publication,
)
from app.db_model.retrievers.resource_retriever import retrieve_all_resources
from app.db_model.retrievers.topic_analysis_run_retriever import (
    create_topic_analysis_run,
    mark_topic_analysis_done,
    mark_topic_analysis_failed,
    mark_topic_analysis_running,
    retrieve_topic_analysis_run,
)

__all__ = [
    'retrieve_all_resources',
    'retrieve_dossiers_by_numbers',
    'retrieve_dossier_summary',
    'persist_dossier_summary',
    'retrieve_onh_publications',
    'retrieve_onh_summary',
    'persist_onh_summary',
    'upsert_onh_publication',
    'create_topic_analysis_run',
    'retrieve_topic_analysis_run',
    'mark_topic_analysis_running',
    'mark_topic_analysis_done',
    'mark_topic_analysis_failed',
]
