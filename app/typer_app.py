"""
Module with typer commands
"""
import json
from pathlib import Path
from time import time

import typer
from ecodev_core import engine
from ecodev_core import logger_get
from ecodev_core import safe_clt
from sqlmodel import Session

from app.methodo.scraper import BASE_URL, scrape_chd_lu_for_dossiers, scrape_dossier
from app.methodo.main_pipeline import dossier_pipeline, OLLAMA_EMBEDDING_MODEL

import logging
logging.getLogger('docling').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

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
def insert_dossier_embedings_command(
    limit: int = typer.Option(None, help="Max number of resources to embed (default: all)"),
) -> None:
    """
    Insert dossier embedings into the database
    """
    with Session(engine) as session:
        dossier_pipeline(session, limit=limit)


@safe_clt
@typer_app.command()
def scrape_onh_command() -> None:
    """
    Scrape ONH (logement.public.lu) publications index and store metadata in DB.
    Falls back gracefully if the site blocks automated access.
    """
    from app.methodo.onh_scraper import scrape_onh_publications
    with Session(engine) as session:
        pubs = scrape_onh_publications(session)
    typer.echo(f"Scraped {len(pubs)} ONH publications.")


@safe_clt
@typer_app.command()
def ingest_onh_from_dir_command(
    pdf_dir: Path = typer.Argument(..., help="Directory containing ONH PDF files"),
) -> None:
    """
    Manual fallback: ingest ONH PDFs placed in a local directory.
    Use when scrape_onh_command fails due to site restrictions.
    """
    from app.methodo.onh_scraper import ingest_onh_pdfs_from_dir
    with Session(engine) as session:
        pubs = ingest_onh_pdfs_from_dir(session, pdf_dir)
    typer.echo(f"Ingested {len(pubs)} ONH publications from {pdf_dir}.")


@safe_clt
@typer_app.command()
def embed_onh_command(
    limit: int = typer.Option(None, help="Max number of publications to embed"),
) -> None:
    """
    Download and embed ONH PDFs into the Chroma vector store.
    Run scrape_onh_command (or ingest_onh_from_dir_command) first.
    """
    from app.methodo.onh_pipeline import onh_pipeline
    with Session(engine) as session:
        onh_pipeline(session, limit=limit)


@safe_clt
@typer_app.command()
def ingest_coalition_agreement_command(
    pdf_path: Path = typer.Argument(..., help="Path to the coalition agreement PDF"),
) -> None:
    """
    Parse and embed the coalition agreement 2023-2028 PDF into Chroma (run once).
    This document provides the KPI baseline for policy analysis.
    """
    from app.methodo.onh_pipeline import coalition_agreement_pipeline
    coalition_agreement_pipeline(pdf_path)
    typer.echo("Coalition agreement ingested successfully.")


@safe_clt
@typer_app.command()
def summarize_laws_command(
    limit: int = typer.Option(None, help="Max number of dossiers to summarize"),
) -> None:
    """
    Pre-generate and cache local-LLM summaries for all dossiers that don't have one yet.
    Run this before analyze_topic_command to avoid on-demand generation delays.
    """
    from app.methodo.chroma import get_create_chroma_vectorstore
    from app.methodo.local_llm import get_local_llm_client
    from app.methodo.summarizer import get_or_generate_law_summary
    from app.db_model.tables.dossier import Dossier
    from sqlmodel import select

    client = get_local_llm_client()
    with Session(engine) as session:
        vectorstore = get_create_chroma_vectorstore(model=OLLAMA_EMBEDDING_MODEL)
        query = select(Dossier)
        if limit:
            query = query.limit(limit)
        dossiers = list(session.exec(query).all())
        typer.echo(f"Summarizing {len(dossiers)} dossiers...")
        for i, dossier in enumerate(dossiers, 1):
            summary = get_or_generate_law_summary(session, vectorstore, client, dossier)
            typer.echo(f"[{i}/{len(dossiers)}] #{dossier.number}: {len(summary)} chars")


@safe_clt
@typer_app.command()
def analyze_topic_command(
    topic: str = typer.Argument(..., help="Topic to analyze, e.g. 'logement abordable'"),
    k_laws: int = typer.Option(5, help="Number of top laws to include"),
    k_onh: int = typer.Option(3, help="Number of top ONH reports to include"),
    k_coalition: int = typer.Option(5, help="Number of coalition agreement excerpts to include"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """
    Analyze how Luxembourg laws address a topic, cross-referencing ONH research
    and coalition agreement promises.
    """
    from app.methodo.topic_analysis_pipeline import topic_analysis_pipeline

    with Session(engine) as session:
        result = topic_analysis_pipeline(
            topic=topic,
            session=session,
            k_laws=k_laws,
            k_onh=k_onh,
            k_coalition=k_coalition,
        )

    if output_json:
        typer.echo(result.model_dump_json(indent=2))
        return

    typer.echo(f"\n{'='*60}")
    typer.echo(f"TOPIC: {result.topic}")
    typer.echo(f"{'='*60}\n")

    if result.coalition_commitments:
        typer.echo("COALITION COMMITMENTS:")
        for c in result.coalition_commitments:
            typer.echo(f"  • {c}")

    typer.echo(f"\nMATCHED LAWS ({len(result.matched_laws)}):")
    for law in result.matched_laws:
        typer.echo(f"  [{law.status}] #{law.dossier_number} — {law.dossier_title} (score: {law.relevance_score:.2f})")

    typer.echo(f"\nMATCHED ONH REPORTS ({len(result.matched_onh_reports)}):")
    for r in result.matched_onh_reports:
        typer.echo(f"  {r.title} (score: {r.relevance_score:.2f})")

    typer.echo(f"\nANALYSIS:\n{result.analysis_text}")

    if result.gaps_identified:
        typer.echo("\nGAPS IDENTIFIED:")
        for g in result.gaps_identified:
            typer.echo(f"  ⚠ {g}")

    typer.echo(f"\nCONCLUSION:\n{result.conclusion}")


if __name__ == '__main__':
    typer_app()
