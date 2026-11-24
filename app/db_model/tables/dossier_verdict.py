from datetime import datetime
from datetime import timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class DossierVerdict(SQLModel, table=True):
    """Per-law verdict on coalition commitments: a LawVerdict (analyzer) as JSON."""
    __tablename__ = "dossier_verdict"

    id: Optional[int] = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id", unique=True, index=True)
    result_json: str
    model_used: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
