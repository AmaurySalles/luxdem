from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.domain_model import TopicAnalysisRunStatus


class TopicAnalysisRun(SQLModel, table=True):
    __tablename__ = "topic_analysis_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic: str = Field(index=True)
    status: TopicAnalysisRunStatus = Field(default=TopicAnalysisRunStatus.Pending)
    result_json: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
