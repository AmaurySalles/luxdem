from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field


from sqlmodel import Relationship

if TYPE_CHECKING:
    from app.db_model.tables.draft_law import DraftLaw

class Resource(SQLModel, table=True):
    """
    A resource is an external document related to the draft law.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    url: str = Field(nullable=False, unique=True)
    
    draft_law_id: Optional[int] = Field(default=None, foreign_key="draft_law.id")
    draft_law: Optional['DraftLaw'] = Relationship(back_populates="resources")
