from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db_model.tables.onh_summary import OntSummary


class OntPublication(SQLModel, table=True):
    __tablename__ = "onh_publication"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    url: str = Field(unique=True, index=True)
    listing_url: str
    published_date: Optional[date] = Field(default=None)
    category: Optional[str] = Field(default=None)

    ai_summary: Optional["OntSummary"] = Relationship(back_populates="publication")
