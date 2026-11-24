"""
Module with typer commands
"""
import json
from collections.abc import Callable
from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import time
from typing import TYPE_CHECKING

import typer
from ecodev_core import engine
from ecodev_core import logger_get
from ecodev_core import safe_clt
from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel import select

from app.methodo.scraper import BASE_URL, scrape_chd_lu_for_dossiers, scrape_dossier
from app.methodo.main_pipeline import dossier_pipeline, OLLAMA_EMBEDDING_MODEL
from app.constants import DATA_DIR

import logging

if TYPE_CHECKING:
    from langchain_chroma import Chroma
    from ollama import Client

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
def relativize_onh_urls_command(
    commit: bool = typer.Option(False, "--commit", help="Apply the rewrite (default: dry-run)"),
) -> None:
    """
    One-off (#55): rewrite legacy `file://.../<file>` onh_publication urls to `onh/<file>`,
    relative to data/downloads. Rows whose file is missing there are refused (left as-is).
    Back up the onh_publication table before --commit.
    """
    from app.db_model.inserters import update_onh_publication_urls
    from app.db_model.retrievers import retrieve_onh_publications
    from app.methodo.onh_paths import ONH_DOWNLOADS_DIR
    from app.methodo.onh_paths import plan_onh_url_rewrites

    with Session(engine) as session:
        rewrites = sorted(plan_onh_url_rewrites(retrieve_onh_publications(session)),
                          key=lambda r: r.id)
        typer.echo(f"{'id':>4}  {'found':<5}  before -> after")
        for r in rewrites:
            typer.echo(f"{r.id:>4}  {'yes' if r.file_found else 'NO':<5}  "
                       f"{r.old_url} -> {r.new_url}")
        ok = {r.id: r.new_url for r in rewrites if r.file_found}
        missing = len(rewrites) - len(ok)
        typer.echo(f"\n{len(rewrites)} legacy rows, {len(ok)} files found under "
                   f"{ONH_DOWNLOADS_DIR}, {missing} refused (file missing)")
        if not commit:
            if ok:
                typer.echo("DRY-RUN: re-run with --commit (back up onh_publication first).")
            return
        typer.echo(f"COMMIT: updated {update_onh_publication_urls(session, ok)} rows.")


@safe_clt
@typer_app.command()
def ingest_coalition_agreement_command(
    pdf_path: Path = typer.Argument(DATA_DIR / "downloads" / "accord_coalition_2023_2028.pdf",
                                    help="Coalition agreement PDF"),
    cache_dir: Path = typer.Option(None, help="Parse cache dir (default: data/parse_cache)"),
) -> None:
    """
    Embed the coalition agreement 2023-2028 PDF into Chroma (run once), from the parse
    cache when the parse box already parsed it. It provides the KPI baseline for policy
    analysis.
    """
    from app.methodo.onh_pipeline import coalition_agreement_pipeline
    from app.methodo.parse_cache import PARSE_CACHE_DIR
    coalition_agreement_pipeline(pdf_path, cache_dir=cache_dir or PARSE_CACHE_DIR)
    typer.echo("Coalition agreement ingested successfully.")


@safe_clt
@typer_app.command()
def export_parse_manifest_command(
    out: Path = typer.Option(DATA_DIR / "parse_manifest.jsonl", help="Manifest to write"),
    dossier_dir: Path = typer.Option(DATA_DIR / "_pilot_a" / "all",
                                     help="Local dossier PDFs, named <dossier number>.pdf"),
) -> None:
    """
    Write the parse box's manifest (#80): every ONH + dossier doc and the coalition
    agreement, with file paths relative to data/. Fails if any doc has no local PDF.
    """
    from app.methodo.parse_manifest import build_manifest
    from app.methodo.parse_manifest import ManifestFilesMissingError
    from app.methodo.parse_manifest import write_manifest
    from app.methodo.parse_worker import LONG_DOC_PAGES
    with Session(engine) as session:
        try:
            rows = build_manifest(session, dossier_dir=dossier_dir)
        except ManifestFilesMissingError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from e
    write_manifest(rows, out)
    long_docs = [r for r in rows if r.page_count > LONG_DOC_PAGES]
    typer.echo(f"{len(rows)} docs ({sum(r.page_count for r in rows)} pages) -> {out}")
    typer.echo(f"long lane (> {LONG_DOC_PAGES} pages): {len(long_docs)}")


@safe_clt
@typer_app.command()
def embed_parity_command(
    remote_host: str = typer.Argument(..., help="Tunnelled GPU Ollama, e.g. "
                                                "http://host.docker.internal:11435"),
    local_host: str = typer.Option("http://host.docker.internal:11434",
                                   help="Laptop Ollama that embeds queries at search time"),
    model: str = typer.Option(OLLAMA_EMBEDDING_MODEL, help="Embedding model"),
    out: Path = typer.Option(DATA_DIR / "embed_parity.json", help="Report to write"),
) -> None:
    """
    Gate before the bulk embed (#47): the GPU box must give the laptop's vectors (min cosine
    >= 0.999, same prompt_eval_count, pinned Ollama version and model digest on both sides).
    """
    from app.methodo.embed_parity import check_parity
    from app.methodo.embed_parity import load_parity_sample
    report = check_parity(model, local_host, remote_host, load_parity_sample())
    summary = json.dumps(report.summary(), indent=1)
    out.write_text(summary)
    typer.echo(summary)
    # safe_clt swallows typer.Exit, so the verdict is printed rather than an exit code
    typer.echo("PARITY PASSED" if report.passed else f"PARITY FAILED: {report.problems}")


@safe_clt
@typer_app.command()
def time_embedding_command(
    host: str = typer.Argument(..., help="Ollama to time, e.g. http://host.docker.internal:11435"),
    model: str = typer.Option(OLLAMA_EMBEDDING_MODEL, help="Embedding model"),
    n_chunks: int = typer.Option(1000, help="Chunks from the fixed timing sample"),
) -> None:
    """Embed a fixed sample of post-fix chunks with production batching, to size the bulk run."""
    from app.methodo.embed_parity import load_timing_sample
    from app.methodo.embed_parity import time_embedding
    result = time_embedding(model, host, load_timing_sample()[:n_chunks])
    typer.echo(json.dumps(result.summary(), indent=1))


MAC_OLLAMA = "http://host.docker.internal:11434"


@safe_clt
@typer_app.command()
def pilot_b_embed_command(
    model: str = typer.Option("snowflake-arctic-embed2", help="Embedding model"),
    host: str = typer.Option(MAC_OLLAMA, help="Ollama that embeds (Mac native, #47)"),
) -> None:
    """Pilot B (#73): embed the pilot batch from the parse cache into a throwaway collection."""
    from app.methodo.chroma import get_create_chroma_vectorstore
    from app.methodo.pilot_b import embed_pilot, PILOT_CHROMA_DIR, PILOT_COLLECTION
    vectorstore = get_create_chroma_vectorstore(model, PILOT_CHROMA_DIR, PILOT_COLLECTION, host)
    n_chunks = embed_pilot(vectorstore)
    typer.echo(f"{n_chunks} chunks in {PILOT_CHROMA_DIR}/{PILOT_COLLECTION}")


@safe_clt
@typer_app.command()
def pilot_b_score_command(
    model: str = typer.Option("snowflake-arctic-embed2", help="Pilot embedding model"),
    baseline_model: str = typer.Option("nomic-embed-text", help="Live collection's model"),
    host: str = typer.Option(MAC_OLLAMA, help="Ollama that embeds the queries"),
    out: Path = typer.Option(DATA_DIR / "pilot_b_report.json", help="Report to write"),
) -> None:
    """
    Pilot B (#73): score the pilot collection and the live pre-fix one on the gold set, run the
    chunk checks on the parse cache, and print the #72 pass-bar verdict.
    """
    from dataclasses import asdict
    from app.constants import CHROMA_COLLECTION, CHROMA_DIR
    from app.methodo.chroma import get_create_chroma_vectorstore
    from app.methodo import pilot_b as pb
    queries = pb.load_gold()
    pilot = pb.score(get_create_chroma_vectorstore(
        model, pb.PILOT_CHROMA_DIR, pb.PILOT_COLLECTION, host), queries)
    live = get_create_chroma_vectorstore(baseline_model, CHROMA_DIR, CHROMA_COLLECTION, host)
    baseline = pb.score(live, queries)
    flipped = pb.flips(baseline, pilot, pb.findable_queries(live, queries))
    checks = pb.check_parse_cache()
    problems = pb.pass_bar_problems(pilot, flipped, checks)
    report = {"pilot": pilot.summary(), "baseline": baseline.summary(), "flips": asdict(flipped),
              "chunk_checks": asdict(checks), "problems": problems}
    summary = json.dumps(report, indent=1, ensure_ascii=False)
    out.write_text(summary)
    typer.echo(summary)
    typer.echo("PILOT B PASSED" if not problems else f"PILOT B FAILED: {problems}")


@safe_clt
@typer_app.command()
def cleanup_stale_chunks_command(
    commit: bool = typer.Option(False, "--commit", help="Embed from cache (default: dry-run)"),
    onh_dir: Path = typer.Option(None, help="Fallback dir for ONH PDFs missing in data/downloads"),
    onh: bool = typer.Option(True, help="Include ONH publications"),
    dossiers: bool = typer.Option(True, help="Include dossiers"),
    limit: int = typer.Option(None, help="Max number of docs per corpus"),
    cache_dir: Path = typer.Option(None, help="Parse cache dir (default: data/parse_cache)"),
) -> None:
    """
    One-off migration (#29, #46). Dry-run (default): parse ONH + dossier docs into the
    parse cache and report vs Chroma, no Chroma writes. --commit: embed-only from the
    cache (no parsing): delete + re-embed changed docs, embed never-embedded ones.
    Back up the Chroma store (config `chroma`) before --commit.
    Coalition is not covered: re-run ingest-coalition-agreement-command instead.
    """
    from app.methodo.parse_cache import PARSE_CACHE_DIR
    from app.methodo.stale_chunk_migration import stale_chunk_migration
    with Session(engine) as session:
        report = stale_chunk_migration(session, commit=commit, onh_dir=onh_dir,
                                       include_onh=onh, include_dossiers=dossiers, limit=limit,
                                       cache_dir=cache_dir or PARSE_CACHE_DIR)

    typer.echo(f"\n{'COMMIT' if commit else 'DRY-RUN'} REPORT")
    if not commit:
        typer.echo(f"  cache hits:   {report.cache_hits} (not reparsed)")
        for env, n in report.cache_envs.most_common():
            typer.echo(f"    {n:>5} parsed with {env}")
        if len(report.cache_envs) > 1:
            typer.echo("  WARNING: cache entries come from more than one parse environment")
    typer.echo(f"  unchanged:    {len(report.unchanged)}")
    typer.echo(f"  not embedded: {len(report.not_embedded)}"
               f" ({sum(new for _, new in report.not_embedded)} chunks to embed)")
    typer.echo(f"  affected:     {len(report.affected)}"
               f" ({sum(old - new for _, old, new in report.affected)} net chunks removed)")
    for label, old, new in report.affected:
        typer.echo(f"    {old:>5} -> {new:<5} {label}")
    for title, rows in (("SUSPICIOUS (0 chunks after parse, untouched)", report.suspicious),
                        ("FAILED TO PARSE (not cached)", report.failed),
                        ("NOT CACHED (skipped, re-run dry run)", report.uncached),
                        ("COUNT MISMATCH AFTER COMMIT", report.count_mismatch)):
        if rows:
            typer.echo(f"  {title}: {len(rows)}")
            for row in rows:
                typer.echo(f"    {row}")
    if not commit and (report.affected or report.not_embedded):
        typer.echo("\nRe-run with --commit to embed from cache (back up the Chroma store first).")


@safe_clt
@typer_app.command()
def summarize_laws_command(
    limit: int = typer.Option(None, help="Max number of dossiers to summarize"),
    workers: int = typer.Option(1, help="Summaries generated at once (pod: OLLAMA_NUM_PARALLEL)"),
) -> None:
    """
    Generate summaries for all dossiers lacking one from the pinned chat model (#98).
    Run this before analyze_topic_command to avoid on-demand generation delays.
    """
    from app.db_model.tables.dossier import Dossier
    from app.methodo.summarizer import get_or_generate_law_summary

    _summarize_all(Dossier, get_or_generate_law_summary, lambda d: f"#{d.number}", limit, workers)


@safe_clt
@typer_app.command()
def summarize_onh_command(
    limit: int = typer.Option(None, help="Max number of ONH publications to summarize"),
    workers: int = typer.Option(1, help="Summaries generated at once (pod: OLLAMA_NUM_PARALLEL)"),
) -> None:
    """Generate summaries for all ONH publications lacking one from the pinned chat model (#98)."""
    from app.db_model.tables.onh_publication import OnhPublication
    from app.methodo.summarizer import get_or_generate_onh_summary

    _summarize_all(OnhPublication, get_or_generate_onh_summary, lambda p: p.title[:60], limit, workers)


class SummariesFailedError(Exception):
    """Documents whose summary failed; the others were saved, so a rerun only redoes these."""

    def __init__(self, failed: dict[str, str]) -> None:
        self.failed = failed  # label -> error
        lines = "\n".join(f"  {label}: {error}" for label, error in failed.items())
        super().__init__(f"{len(failed)} summaries failed:\n{lines}")


def _summarize_all(model: type[SQLModel],
                   generate: Callable[[Session, "Chroma", "Client", SQLModel], str],
                   label: Callable[[SQLModel], str],
                   limit: int | None,
                   workers: int,
                   ) -> None:
    """
    Summarize every `model` row (dossiers or ONH publications); cached summaries from the pinned model are kept.

    Purpose: shared loop of summarize_laws_command and summarize_onh_command.

    NOTE: `workers` requests run at once; the chat host's Ollama needs OLLAMA_NUM_PARALLEL
    of at least that, or they queue (#98). Each worker uses its own DB session.

    Raises:
        SummariesFailedError: after the run, if any document failed.
    """
    from app.methodo.chroma import get_create_chroma_vectorstore
    from app.methodo.local_llm import CHAT_MODEL_ID, get_local_llm_client

    client = get_local_llm_client()
    vectorstore = get_create_chroma_vectorstore(model=OLLAMA_EMBEDDING_MODEL)
    with Session(engine) as session:
        docs = {doc.id: label(doc) for doc in session.exec(select(model).limit(limit))}

    def summarize(doc_id: int) -> int:
        with Session(engine) as worker_session:
            return len(generate(worker_session, vectorstore, client, worker_session.get(model, doc_id)))

    typer.echo(f"Summarizing {len(docs)} documents with {CHAT_MODEL_ID}, {workers} at once...")
    failed: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(summarize, doc_id): doc_label for doc_id, doc_label in docs.items()}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                typer.echo(f"[{i}/{len(docs)}] {futures[future]}: {future.result()} chars")
            except Exception as error:  # noqa: BLE001 — one bad doc must not stop a 3 h GPU run
                log.exception(f"Summary failed for {futures[future]}")
                failed[futures[future]] = repr(error)
    if failed:
        raise SummariesFailedError(failed)


@safe_clt
@typer_app.command()
def analyze_dossiers_command(
    numbers: list[str] = typer.Argument(..., help="Dossier numbers, e.g. 8357 8358"),
) -> None:
    """
    Per-law verdicts on coalition commitments, stored for the dossier pages.
    """
    from app.db_model.retrievers.dossier_retriever import retrieve_dossiers_by_numbers
    from app.methodo.dossier_verdict_pipeline import dossier_verdict_pipeline

    with Session(engine) as session:
        dossiers = retrieve_dossiers_by_numbers(session, numbers)
        missing = set(numbers) - {d.number for d in dossiers}
        if missing:
            typer.echo(f"Unknown dossiers: {sorted(missing)}")
            return
        dossier_verdict_pipeline(session, dossiers)


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


@safe_clt
@typer_app.command()
def import_government_command() -> None:
    """
    Import government mandates and party statements from gouvernement.lu (#119).
    """
    from app.methodo.government import import_government

    with Session(engine) as session:
        mandates, statements = import_government(session)
    typer.echo(f"Mandates: {mandates}, party statements: {statements}")


@safe_clt
@typer_app.command()
def import_chd_opendata_command() -> None:
    """
    Import CHD open data (votes, commission memberships) from data.public.lu, replacing the
    previous import, then report what could not be linked (#119).
    """
    from collections import Counter

    from app.db_model import Dossier
    from app.methodo.chd_opendata import import_chd_opendata

    with Session(engine) as session:
        ballots, memberships = import_chd_opendata(session)
        our_numbers = set(session.exec(select(Dossier.number)).all())
        voted = {n for b in ballots if not b.is_ambiguous for n in b.dossier_numbers}
        seats = [s for b in ballots if not b.is_ambiguous for s in b.seats]
        typer.echo(f"Ballots: {len(ballots)} {dict(Counter(b.kind.value for b in ballots))}")
        typer.echo(f"Ambiguous (left out of records): "
                   f"{[b.label for b in ballots if b.is_ambiguous]}")
        typer.echo(f"Seats: {len(seats)}, proxy-holder seats awaiting bulletins: "
                   f"{sum(not s.is_own_vote for s in seats)}")
        typer.echo(f"Our dossiers with a ballot: {len(our_numbers & voted)}/{len(our_numbers)}")
        typer.echo(f"Commission memberships: {len(memberships)}")
        _report_proxies(session)


def _report_proxies(session: Session) -> None:
    from app.methodo.chd_accountability import resolve_proxies

    report = resolve_proxies(session)
    typer.echo(f"Bulletins resolved: {len(report.resolved)}, "
               f"seats attributed: {report.seats_attributed}")
    typer.echo(f"Bulletins without a matching ballot: {report.no_ballot}")
    typer.echo(f"Bulletins failed: {report.failed}")


@safe_clt
@typer_app.command()
def scrape_dossier_pages_command(
    limit: int = typer.Option(None, help="Max number of dossiers (default: all)"),
) -> None:
    """
    Scrape commissions, rapporteurs and vote bulletin links from our dossiers' chd.lu pages,
    then attribute proxy seats from the bulletins (#119).
    """
    from app.db_model import Dossier
    from app.methodo.chd_accountability import scrape_dossier_pages

    with Session(engine) as session:
        dossiers = list(session.exec(select(Dossier).order_by(Dossier.number).limit(limit)).all())
        failed = scrape_dossier_pages(session, dossiers)
        typer.echo(f"Pages scraped: {len(dossiers) - len(failed)}/{len(dossiers)}, "
                   f"failed: {failed}")
        _report_proxies(session)


@safe_clt
@typer_app.command()
def resolve_proxies_command() -> None:
    """Attribute proxy seats from the vote bulletins already scraped (#119)."""
    with Session(engine) as session:
        _report_proxies(session)


if __name__ == '__main__':
    typer_app()
