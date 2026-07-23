"""
Routes to launch a topic analysis in the background and poll for its result.
"""
from datetime import datetime

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ecodev_core import engine
from ecodev_core import get_session
from ecodev_core import log_critical
from ecodev_core import logger_get

from app.db_model.retrievers import create_topic_analysis_run
from app.db_model.retrievers import mark_topic_analysis_done
from app.db_model.retrievers import mark_topic_analysis_failed
from app.db_model.retrievers import mark_topic_analysis_running
from app.db_model.retrievers import retrieve_topic_analysis_run
from app.domain_model import TopicAnalysisRunStatus
from app.methodo.analyzer import TopicAnalysisResult
from app.methodo.topic_analysis_pipeline import topic_analysis_pipeline

log = logger_get(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class TopicAnalysisRequest(BaseModel):
    topic: str
    k_laws: int = 5
    k_onh: int = 3
    k_coalition: int = 5


class TopicAnalysisLaunchResponse(BaseModel):
    success: bool
    error: str | None = None
    run_id: int | None = None


class TopicAnalysisStatusResponse(BaseModel):
    run_id: int
    topic: str
    status: TopicAnalysisRunStatus
    result: TopicAnalysisResult | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


@router.post("/topic", response_model=TopicAnalysisLaunchResponse, status_code=202)
def launch_topic_analysis(
    request: TopicAnalysisRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> TopicAnalysisLaunchResponse:
    topic = request.topic.strip()
    if not topic:
        return TopicAnalysisLaunchResponse(success=False, error="topic must not be empty")

    try:
        run = create_topic_analysis_run(session, topic)
    except Exception as error:
        log_critical(f"Failed to create topic analysis run: {error}", log)
        return TopicAnalysisLaunchResponse(success=False, error=str(error))

    background_tasks.add_task(
        _run_topic_analysis_background,
        run.id,
        topic,
        request.k_laws,
        request.k_onh,
        request.k_coalition,
    )
    return TopicAnalysisLaunchResponse(success=True, run_id=run.id)


@router.get("/topic/{run_id}", response_model=TopicAnalysisStatusResponse)
def get_topic_analysis_status(
    run_id: int,
    session: Session = Depends(get_session),
) -> TopicAnalysisStatusResponse:
    run = retrieve_topic_analysis_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No topic analysis run with id={run_id}")

    result = TopicAnalysisResult.model_validate_json(run.result_json) if run.result_json else None
    return TopicAnalysisStatusResponse(
        run_id=run.id,
        topic=run.topic,
        status=run.status,
        result=result,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _run_topic_analysis_background(
    run_id: int,
    topic: str,
    k_laws: int,
    k_onh: int,
    k_coalition: int,
) -> None:
    """
    Runs the slow pipeline out-of-request. Opens its own DB session since BackgroundTasks
    execute after the response has been sent and the request-scoped session is closed.
    """
    with Session(engine) as session:
        mark_topic_analysis_running(session, run_id)
        try:
            result = topic_analysis_pipeline(
                topic=topic,
                session=session,
                k_laws=k_laws,
                k_onh=k_onh,
                k_coalition=k_coalition,
            )
            mark_topic_analysis_done(session, run_id, result.model_dump_json())
        except Exception as error:
            log_critical(f"Topic analysis failed for run_id={run_id} topic='{topic}': {error}", log)
            mark_topic_analysis_failed(session, run_id, str(error))
