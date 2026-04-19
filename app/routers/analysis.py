from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ecodev_core import engine
from app.methodo.analyzer import TopicAnalysisResult
from app.methodo.topic_analysis_pipeline import topic_analysis_pipeline

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class TopicAnalysisRequest(BaseModel):
    topic: str
    k_laws: int = 5
    k_onh: int = 3
    k_coalition: int = 5


def get_session():
    with Session(engine) as session:
        yield session


@router.post("/topic", response_model=TopicAnalysisResult)
def analyze_topic_endpoint(
    request: TopicAnalysisRequest,
    session: Session = Depends(get_session),
) -> TopicAnalysisResult:
    return topic_analysis_pipeline(
        topic=request.topic,
        session=session,
        k_laws=request.k_laws,
        k_onh=request.k_onh,
        k_coalition=request.k_coalition,
    )
