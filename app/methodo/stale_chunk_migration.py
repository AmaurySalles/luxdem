"""
One-off migration: re-embed ONH + dossier docs whose chunking changed after the
table-shredding fix (#31), deleting their stale Chroma chunks first (see #29), and
embed the docs that were never embedded at all (#46).

Two passes, so a rented GPU never sits idle while Docling parses (#46):
- dry-run (default, laptop): parse every target, write the chunks to the parse cache
  (`parse_cache.py`), compare with Chroma and report. Never writes to Chroma. Docs
  that already have a valid cache entry are not reparsed, so an interrupted run resumes.
- `--commit` (GPU up): reads chunks from the cache only, never parses. Deletes +
  re-embeds affected docs and embeds never-embedded ones. Targets without a valid
  cache entry (missing, or stale after a parser change) are skipped and reported.

Chunk ids are `md5(source_url::chunk_index)`, so a doc that now yields fewer chunks
would keep its old high-index chunks forever if simply re-embedded. Coalition is not
covered here: `coalition_agreement_pipeline` already wipes + re-ingests on every run.

The vectorstore comes from `get_create_chroma_vectorstore`, so whichever collection it
points at is the one compared against. An empty collection just means every doc is
"not embedded" and gets embedded on `--commit`.
"""
import hashlib
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Callable

from ecodev_core import logger_get
from langchain_chroma import Chroma
from sqlmodel import Session

from app.db_model.retrievers import retrieve_all_resources
from app.db_model.retrievers.onh_retriever import retrieve_onh_publications
from app.methodo.chroma import embed_and_store_in_chroma
from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.main_pipeline import OLLAMA_EMBEDDING_MODEL
from app.methodo.onh_pipeline import _get_onh_metadata
from app.methodo.onh_pipeline import ONH_MIN_CHUNK_WORDS
from app.methodo.parse_cache import load_cached_chunks
from app.methodo.parse_cache import parse_fingerprint
from app.methodo.parse_cache import PARSE_CACHE_DIR
from app.methodo.parse_cache import save_cached_chunks
from app.methodo.parsing.docling_parser import parse_with_docling
from app.methodo.parsing.metadata import get_resource_metadata

log = logger_get(__name__)


@dataclass
class MigrationTarget:
    """
    One doc to check: `source_url` keys its Chroma chunks and cache entry, `parse`
    reparses it, `fingerprint` says whether a cache entry is still valid.
    """
    label: str
    source_url: str
    parse: Callable[[], list[dict[str, Any]]]
    fingerprint: str


@dataclass
class MigrationReport:
    unchanged: list[str] = field(default_factory=list)
    not_embedded: list[tuple[str, int]] = field(default_factory=list)  # (label, new)
    affected: list[tuple[str, int, int]] = field(default_factory=list)  # (label, old, new)
    suspicious: list[tuple[str, int]] = field(default_factory=list)  # (label, old) -> 0 new
    failed: list[tuple[str, str]] = field(default_factory=list)  # (label, error)
    uncached: list[str] = field(default_factory=list)  # commit only: no valid cache entry
    count_mismatch: list[tuple[str, int, int]] = field(default_factory=list)  # post-commit
    cache_hits: int = 0  # dry-run only: targets not reparsed


def _chunk_id(source_url: str, index: int) -> str:
    # must match embed_and_store_in_chroma's id scheme
    return hashlib.md5(f"{source_url}::{index}".encode()).hexdigest()


def _is_changed(stored: dict[str, Any], source_url: str, chunks: list[dict[str, Any]]) -> bool:
    """Changed if the id set or any chunk's text differs (catches same-count re-splits too)."""
    new_ids = [_chunk_id(source_url, i) for i in range(len(chunks))]
    if set(stored["ids"]) != set(new_ids):
        return True
    stored_text = dict(zip(stored["ids"], stored["documents"]))
    return any(stored_text[i] != c["page_content"] for i, c in zip(new_ids, chunks))


def _get_chunks(target: MigrationTarget, cache_dir: Path, commit: bool,
                report: MigrationReport) -> list[dict[str, Any]] | None:
    """Cached chunks, else (dry-run only) parse + cache. None if unavailable (reported)."""
    chunks = load_cached_chunks(cache_dir, target.source_url, target.fingerprint)
    if chunks is not None:
        if not commit:
            report.cache_hits += 1
        return chunks
    if commit:
        log.warning("   → no valid cache entry, skipping (re-run the dry run first)")
        report.uncached.append(target.label)
        return None
    try:
        chunks = target.parse()
    except Exception as e:
        log.error(f"   → parse failed: {e}")
        report.failed.append((target.label, str(e)))
        return None
    save_cached_chunks(cache_dir, target.source_url, target.label, target.fingerprint, chunks)
    return chunks


def migrate_stale_chunks(targets: list[MigrationTarget],
                         vectorstore: Chroma,
                         cache_dir: Path = PARSE_CACHE_DIR,
                         commit: bool = False) -> MigrationReport:
    """
    Dry-run: parse (or reuse cache), cache and classify each target. Commit: classify
    from cache only, then delete + re-embed affected docs and embed never-embedded ones.
    """
    report = MigrationReport()
    for n, target in enumerate(targets, 1):
        log.info(f"[{n}/{len(targets)}] {target.label}")
        chunks = _get_chunks(target, cache_dir, commit, report)
        if chunks is None:
            continue

        stored = vectorstore.get(where={"source_url": target.source_url},
                                 include=["documents"])
        old_count = len(stored["ids"])
        if not chunks:
            # likely a silent parse failure: never wipe (or "embed") a doc for nothing
            log.warning(f"   → {old_count} chunks -> 0 after parse, leaving untouched")
            report.suspicious.append((target.label, old_count))
            continue

        if not old_count:
            log.info(f"   → not embedded: {len(chunks)} chunks to embed")
            report.not_embedded.append((target.label, len(chunks)))
        elif not _is_changed(stored, target.source_url, chunks):
            report.unchanged.append(target.label)
            continue
        else:
            log.info(f"   → affected: {old_count} -> {len(chunks)} chunks")
            report.affected.append((target.label, old_count, len(chunks)))
        if not commit:
            continue

        if old_count:
            vectorstore.delete(ids=stored["ids"])
        embed_and_store_in_chroma(chunks, vectorstore)
        stored_after = len(vectorstore.get(where={"source_url": target.source_url})["ids"])
        if stored_after != len(chunks):
            log.error(f"   → stored {stored_after} chunks, expected {len(chunks)}")
            report.count_mismatch.append((target.label, stored_after, len(chunks)))
    return report


def _resolve_onh_source(url: str, onh_dir: Path | None) -> str:
    """ONH urls in the DB can be local paths from another machine: fall back to onh_dir."""
    source = url.removeprefix("file://")
    if onh_dir is not None and not source.startswith("http") and not Path(source).exists():
        return str(onh_dir / Path(source).name)
    return source


def collect_targets(session: Session,
                    onh_dir: Path | None = None,
                    include_onh: bool = True,
                    include_dossiers: bool = True,
                    limit: int | None = None) -> list[MigrationTarget]:
    """Build targets with the same parse settings as onh_pipeline / dossier_pipeline."""
    targets: list[MigrationTarget] = []
    if include_onh:
        for pub in retrieve_onh_publications(session, limit=limit):
            source = _resolve_onh_source(pub.url, onh_dir)
            metadata = _get_onh_metadata(pub)
            targets.append(MigrationTarget(
                label=f"onh: {pub.title}",
                source_url=pub.url,
                parse=lambda s=source, m=metadata: parse_with_docling(
                    s, m, min_chunk_words=ONH_MIN_CHUNK_WORDS),
                fingerprint=parse_fingerprint(metadata, min_chunk_words=ONH_MIN_CHUNK_WORDS),
            ))
    if include_dossiers:
        seen_urls: set[str] = set()
        for item in retrieve_all_resources(session, title="Document de dépôt", limit=limit):
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            metadata = get_resource_metadata(item)
            targets.append(MigrationTarget(
                label=f"dossier #{item.dossier.number}: {item.url}",
                source_url=item.url,
                parse=lambda u=item.url, m=metadata: parse_with_docling(u, m),
                fingerprint=parse_fingerprint(metadata),
            ))
    return targets


def stale_chunk_migration(session: Session,
                          commit: bool = False,
                          onh_dir: Path | None = None,
                          include_onh: bool = True,
                          include_dossiers: bool = True,
                          limit: int | None = None,
                          cache_dir: Path = PARSE_CACHE_DIR,
                          embedding_model: str = OLLAMA_EMBEDDING_MODEL) -> MigrationReport:
    targets = collect_targets(session, onh_dir, include_onh, include_dossiers, limit)
    vectorstore = get_create_chroma_vectorstore(model=embedding_model)
    return migrate_stale_chunks(targets, vectorstore, cache_dir=cache_dir, commit=commit)
