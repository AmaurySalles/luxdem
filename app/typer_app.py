"""
Module with typer commands
"""
from time import time
from urllib.parse import urljoin
import typer
from ecodev_core import engine
from ecodev_core import logger_get
from ecodev_core import safe_clt
from sqlmodel import Session

from app.methodo.scraper import BASE_URL, scrape_chd_lu_for_dossiers, scrape_dossier
from app.methodo.main_pipeline import dossier_pipeline


typer_app = typer.Typer()
log = logger_get(__name__)


@safe_clt
@typer_app.command()
def scrape_chd_lu_for_dossier_command() -> None:
    """
    Scrape chd.lu for dossiers metadata
    """
    with Session(engine) as session:
        scrape_chd_lu_for_dossiers(session)


@safe_clt
@typer_app.command()
def insert_dossier_embedings_command() -> None:
    """
    Insert dossier embedings into the database
    """
    with Session(engine) as session:
        dossier_pipeline(session)


if __name__ == '__main__':
    typer_app()
