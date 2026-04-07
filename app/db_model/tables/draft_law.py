from datetime import datetime, date
from typing import TYPE_CHECKING, Any, Dict, Optional



from app.domain_model import LawStatus
from app.domain_model import LawType
from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from app.db_model.tables.resources import Resource


class DraftLaw(SQLModel, table=True):
    __tablename__ = "draft_law"

    id: Optional[int] = Field(default=None, primary_key=True)
    law_number: str  # Some law numbers end with 'a' or 'b'
    law_title: str
    law_type: str
    law_deposit_date: Optional[date] = Field(default=None)
    law_evacuation_date: Optional[date] = Field(default=None)
    law_status: Optional[LawStatus] = Field(default=None)
    law_content: Optional[str] = Field(default=None)
    law_authors: Optional[str] = Field(default=None)
    resources: list['Resource'] = Relationship(back_populates="draft_law")
    # Relationship (adjust back_populates according to your Commitment model)
    # commitments: list["Commitment"] = Relationship(back_populates="draft_laws", link_model=DraftLawCommitmentLink)
    # commitments: list["Commitment"] = Relationship(back_populates="draft_laws", link_model=DraftLawCommitmentLink)
