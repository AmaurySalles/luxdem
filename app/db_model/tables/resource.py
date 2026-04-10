from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field


from sqlmodel import Relationship

if TYPE_CHECKING:
    from app.db_model.tables.dossier import Dossier

class Resource(SQLModel, table=True):
    """
    A resource is an external document related to the dossier.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    url: str = Field(nullable=False)
    
    dossier_id: Optional[int] = Field(default=None, foreign_key="dossier.id")
    dossier: Optional['Dossier'] = Relationship(back_populates="resources")
