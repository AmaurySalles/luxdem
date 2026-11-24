"""
Tables mirroring CHD open data on data.public.lu: deputies, commission memberships and
per-seat plenary votes (#119). Re-imported as a whole by `import-chd-opendata`.
"""
from datetime import date
from datetime import datetime
from datetime import timezone

from sqlmodel import Field
from sqlmodel import Relationship
from sqlmodel import SQLModel
from sqlmodel import UniqueConstraint

from app.domain_model.ballot import BallotKind
from app.domain_model.ballot import PoliticalGroupType
from app.domain_model.ballot import VoteChoice
from app.domain_model.ballot import VoteStage


class OpenDataImport(SQLModel, table=True):
    """
    One import of a CHD dataset: the attribution (CC licence) and freshness shown with the data.
    """
    __tablename__ = "open_data_import"

    id: int | None = Field(default=None, primary_key=True)
    dataset: str = Field(index=True)
    source_url: str
    row_count: int
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Deputy(SQLModel, table=True):
    """A person who sat in the Chambre, identified by name as CHD open data has no person id."""
    __tablename__ = "deputy"
    __table_args__ = (UniqueConstraint("last_name", "first_name"),)

    id: int | None = Field(default=None, primary_key=True)
    last_name: str
    first_name: str


class CommissionMembership(SQLModel, table=True):
    """A deputy's role in a commission over a period (CHD dataset 104)."""
    __tablename__ = "commission_membership"

    id: int | None = Field(default=None, primary_key=True)
    commission_chd_id: int = Field(index=True)
    commission_type: str
    commission_title: str = Field(index=True)
    commission_start: date | None = None  # missing for 5 rows in dataset 104
    commission_end: date | None = None
    deputy_id: int = Field(foreign_key="deputy.id", index=True)
    role: str
    role_start: date
    role_end: date | None = None
    political_group: str


class Ballot(SQLModel, table=True):
    """
    One plenary ballot (CHD dataset 109), keyed by label and time.

    NOTE: is_ambiguous marks labels that merge several ballots (a deputy listed more than twice):
    their votes cannot be attributed and are left out of individual records.
    """
    __tablename__ = "ballot"
    __table_args__ = (UniqueConstraint("label", "held_at"),)

    id: int | None = Field(default=None, primary_key=True)
    label: str
    held_at: datetime = Field(index=True)
    stage: VoteStage
    kind: BallotKind
    is_ambiguous: bool = False

    dossiers: list["BallotDossier"] = Relationship(cascade_delete=True)
    seats: list["SeatVote"] = Relationship(cascade_delete=True)


class BallotDossier(SQLModel, table=True):
    """Dossier numbers a ballot label refers to (one label can name several)."""
    __tablename__ = "ballot_dossier"

    ballot_id: int | None = Field(default=None, foreign_key="ballot.id", primary_key=True)
    dossier_number: str = Field(primary_key=True, index=True)


class SeatVote(SQLModel, table=True):
    """
    One seat's vote in a ballot, as CHD open data lists it.

    NOTE: open data names who cast the vote, not whose vote it is. A deputy holding a proxy
    appears twice and the absent deputy not at all. `on_behalf_of_id` is set when that is
    certain (deputy listed once) and left empty for the two seats of a proxy holder until the
    session minutes resolve them.
    """
    __tablename__ = "seat_vote"

    id: int | None = Field(default=None, primary_key=True)
    ballot_id: int | None = Field(default=None, foreign_key="ballot.id", index=True)
    cast_by_id: int = Field(foreign_key="deputy.id", index=True)
    on_behalf_of_id: int | None = Field(default=None, foreign_key="deputy.id", index=True)
    choice: VoteChoice
    political_group: str
    political_group_type: PoliticalGroupType
