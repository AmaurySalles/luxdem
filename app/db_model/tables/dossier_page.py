"""
Facts scraped from a dossier's chd.lu page that CHD open data lacks (#119): the commissions that
handled it, its rapporteurs, its vote bulletins and its dated activities.
Replaced on each scrape of the page.
"""
from datetime import date

from sqlmodel import Field
from sqlmodel import SQLModel


class DossierCommission(SQLModel, table=True):
    """A commission the dossier was sent to, by title as on chd.lu (dataset 104 has no page id)."""
    __tablename__ = "dossier_commission"

    dossier_id: int = Field(foreign_key="dossier.id", primary_key=True)
    commission_title: str = Field(primary_key=True)


class DossierRapporteur(SQLModel, table=True):
    """A rapporteur as named on chd.lu, linked to a deputy when the name matches one."""
    __tablename__ = "dossier_rapporteur"

    dossier_id: int = Field(foreign_key="dossier.id", primary_key=True)
    name: str = Field(primary_key=True)
    deputy_id: int | None = Field(default=None, foreign_key="deputy.id")


class VoteBulletin(SQLModel, table=True):
    """
    A 'Bulletin de Vote (Vote Public)' PDF linked from the dossier page.

    NOTE: not tied to a ballot id, since ballots are re-created on each open data import;
    the bulletin's own date and label find its ballot.
    """
    __tablename__ = "vote_bulletin"

    dossier_id: int = Field(foreign_key="dossier.id", primary_key=True)
    url: str = Field(primary_key=True)


class DossierActivity(SQLModel, table=True):
    """
    One dated step of the legislative procedure, from the page's 'Activités liées au dossier'.

    NOTE: document URLs carry upload dates (re-uploads, e.g. 8535's rapport dated after the
    vote); these are the procedure's own dates.
    """
    __tablename__ = "dossier_activity"

    id: int | None = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id", index=True)
    day: date
    description: str
    actor: str
