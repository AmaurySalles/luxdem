from datetime import datetime

from sqlmodel import Session

from app.db_model.tables.topic_analysis_run import TopicAnalysisRun
from app.domain_model import TopicAnalysisRunStatus


def create_topic_analysis_run(session: Session, topic: str) -> TopicAnalysisRun:
    record = TopicAnalysisRun(topic=topic, status=TopicAnalysisRunStatus.Pending)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def retrieve_topic_analysis_run(session: Session, run_id: int) -> TopicAnalysisRun | None:
    return session.get(TopicAnalysisRun, run_id)


def mark_topic_analysis_running(session: Session, run_id: int) -> None:
    _update_run(session, run_id, status=TopicAnalysisRunStatus.Running)


def mark_topic_analysis_done(session: Session, run_id: int, result_json: str) -> None:
    _update_run(session, run_id, status=TopicAnalysisRunStatus.Done, result_json=result_json)


def mark_topic_analysis_failed(session: Session, run_id: int, error: str) -> None:
    _update_run(session, run_id, status=TopicAnalysisRunStatus.Failed, error=error)


def _update_run(
    session: Session,
    run_id: int,
    *,
    status: TopicAnalysisRunStatus,
    result_json: str | None = None,
    error: str | None = None,
) -> None:
    record = session.get(TopicAnalysisRun, run_id)
    if record is None:
        return
    record.status = status
    if result_json is not None:
        record.result_json = result_json
    if error is not None:
        record.error = error
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
