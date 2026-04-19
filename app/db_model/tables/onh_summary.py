from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db_model.tables.onh_publication import OntPublication


class OntSummary(SQLModel, table=True):
    __tablename__ = "onh_summary"

    id: Optional[int] = Field(default=None, primary_key=True)
    onh_id: int = Field(foreign_key="onh_publication.id", unique=True, index=True)
    summary: str
    model_used: str = Field(default="claude-sonnet-4-6")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    publication: Optional["OntPublication"] = Relationship(back_populates="ai_summary")
