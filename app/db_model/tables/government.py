"""
Government members (#119): mandates and party statements from gouvernement.lu.
Re-imported as a whole by `import-government-command`.
"""
from datetime import date
from datetime import datetime
from datetime import timezone

from sqlmodel import Field
from sqlmodel import SQLModel


class GovernmentMandate(SQLModel, table=True):
    """One function a person held in government over a period."""
    __tablename__ = "government_mandate"

    id: int | None = Field(default=None, primary_key=True)
    last_name: str = Field(index=True)
    first_name: str
    function: str  # 'Ministre du Logement et de l'Aménagement du territoire'
    start: date
    end: date | None = None  # None: in office
    source_url: str
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PartyStatement(SQLModel, table=True):
    """A minister's party as their official biography states it, quoted."""
    __tablename__ = "party_statement"

    id: int | None = Field(default=None, primary_key=True)
    last_name: str = Field(index=True)
    first_name: str
    party: str  # abbreviation, as in CHD open data: 'DP', 'CSV'
    quote: str  # 'Membre du DP depuis 1994'
    source_url: str
