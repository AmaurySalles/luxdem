from datetime import datetime, date
from typing import TYPE_CHECKING, Any, Dict, Optional



from app.domain_model import DossierStatus
from app.domain_model import DossierType
from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from app.db_model.tables.resource import Resource
    from app.db_model.tables.dossier_summary import DossierSummary


class Dossier(SQLModel, table=True):
    __tablename__ = "dossier"

    id: Optional[int] = Field(default=None, primary_key=True)
    number: str  # Some law numbers end with 'a' or 'b'
    title: str
    type: str
    deposit_date: Optional[date] = Field(default=None)
    evacuation_date: Optional[date] = Field(default=None)
    status: Optional[DossierStatus] = Field(default=None)
    content: Optional[str] = Field(default=None)
    authors: Optional[str] = Field(default=None)
    resources: list['Resource'] = Relationship(back_populates="dossier")
    ai_summary: Optional['DossierSummary'] = Relationship(back_populates="dossier")
   