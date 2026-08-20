from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db_model.tables.dossier import Dossier


class DossierSummary(SQLModel, table=True):
    __tablename__ = "dossier_summary"

    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id", unique=True, index=True)
    summary: str
    model_used: str = Field(default="claude-sonnet-4-6")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    dossier: Optional["Dossier"] = Relationship(back_populates="ai_summary")
