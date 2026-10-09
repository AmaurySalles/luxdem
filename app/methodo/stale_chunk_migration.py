"""
One-off migration: re-embed ONH + dossier docs whose chunking changed after the
table-shredding fix (#31), deleting their stale Chroma chunks first (see #29).

Chunk ids are `md5(source_url::chunk_index)`, so a doc that now yields fewer chunks
would keep its old high-index chunks forever if simply re-embedded. Coalition is not
covered here: `coalition_agreement_pipeline` already wipes + re-ingests on every run.
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
from app.methodo.parsing.docling_parser import parse_with_docling
from app.methodo.parsing.metadata import get_resource_metadata

log = logger_get(__name__)


@dataclass
class MigrationTarget:
    """One doc to check: `source_url` keys its Chroma chunks, `parse` reparses it."""
    label: str
    source_url: str
    parse: Callable[[], list[dict[str, Any]]]


@dataclass
class MigrationReport:
    unchanged: list[str] = field(default_factory=list)
    not_embedded: list[str] = field(default_factory=list)
    affected: list[tuple[str, int, int]] = field(default_factory=list)  # (label, old, new)
    suspicious: list[tuple[str, int]] = field(default_factory=list)  # (label, old) -> 0 new
    failed: list[tuple[str, str]] = field(default_factory=list)  # (label, error)
    count_mismatch: list[tuple[str, int, int]] = field(default_factory=list)  # post-commit


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


def migrate_stale_chunks(targets: list[MigrationTarget],
                         vectorstore: Chroma,
                         commit: bool = False) -> MigrationReport:
    """Reparse each target; in commit mode delete + re-embed the ones whose chunks changed."""
    report = MigrationReport()
    for n, target in enumerate(targets, 1):
        log.info(f"[{n}/{len(targets)}] {target.label}")
        stored = vectorstore.get(where={"source_url": target.source_url},
                                 include=["documents"])
        old_count = len(stored["ids"])
        if not old_count:
            # never embedded: the normal pipelines will pick it up with the fix already in
            report.not_embedded.append(target.label)
            continue

        try:
            chunks = target.parse()
        except Exception as e:
            log.error(f"   → parse failed: {e}")
            report.failed.append((target.label, str(e)))
            continue

        if not chunks:
            # likely a silent parse failure: never wipe a doc's chunks for nothing
            log.warning(f"   → {old_count} chunks -> 0 after reparse, leaving untouched")
            report.suspicious.append((target.label, old_count))
            continue

        if not _is_changed(stored, target.source_url, chunks):
            report.unchanged.append(target.label)
            continue

        log.info(f"   → affected: {old_count} -> {len(chunks)} chunks")
        report.affected.append((target.label, old_count, len(chunks)))
        if not commit:
            continue

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
            ))
    return targets


def stale_chunk_migration(session: Session,
                          commit: bool = False,
                          onh_dir: Path | None = None,
                          include_onh: bool = True,
                          include_dossiers: bool = True,
                          limit: int | None = None,
                          embedding_model: str = OLLAMA_EMBEDDING_MODEL) -> MigrationReport:
    targets = collect_targets(session, onh_dir, include_onh, include_dossiers, limit)
    vectorstore = get_create_chroma_vectorstore(model=embedding_model)
    return migrate_stale_chunks(targets, vectorstore, commit=commit)
