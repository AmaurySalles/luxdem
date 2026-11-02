"""
On-disk cache of Docling parse results, so parsing (slow, free on the laptop) and
embedding (needs the rented GPU) can run as separate passes (#46).

One JSON file per doc: `<cache_dir>/<md5(source_url)>.json` holding `source_url`,
`label`, `fingerprint`, `parse_env` and `chunks` (the exact `parse_with_docling` output).

A cache entry is only valid if its fingerprint matches the current one, which hashes
the `app/methodo/parsing/*.py` sources (chunker/tokenizer settings live there), the
installed docling, docling-core, docling-parse and torch versions, the parse args
(`min_chunk_words`, `content_start_page`) and the doc's DB metadata. Any of these
changing invalidates the entry, so a parser change between the parse and embed passes
can't slip through.

NOTE: the torch device/build (`+cpu`, `+cu128`, MPS) is recorded in `parse_env`, not
hashed: the bulk parse runs on a CUDA box (#71) and the laptop dry run must still hit
those entries. The dry run reports entries per `parse_env`, so a mix is visible.

Docs whose parse failed on the parse box (#77) are listed in `<cache_dir>/failed.jsonl`.
"""
import hashlib
import json
import os
import platform
from dataclasses import asdict
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
from pathlib import Path
from typing import Any

import torch
from ecodev_core import logger_get

from app.constants import DATA_DIR
from app.methodo.parsing.docling_parser import parse_with_docling

log = logger_get(__name__)

PARSE_CACHE_DIR = DATA_DIR / "parse_cache"
FAILED_FILE = "failed.jsonl"
_PARSING_DIR = Path(__file__).parent / "parsing"


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"


def _parsing_source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(_PARSING_DIR.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_env() -> dict[str, str]:
    """Where a parse ran (torch build + device), stored with each entry but not hashed."""
    if torch.cuda.is_available():
        device = f"cuda:{torch.cuda.get_device_name(0)}"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    return {"torch": torch.__version__, "device": device, "host": platform.node()}


def parse_fingerprint(metadata: dict[str, Any],
                      min_chunk_words: int | None = None,
                      content_start_page: int = 1) -> str:
    """Hash of everything that determines `parse_with_docling`'s output for one doc."""
    parts = {
        "parsing_source": _parsing_source_hash(),
        "docling": _pkg_version("docling"),
        "docling_core": _pkg_version("docling-core"),
        "docling_parse": _pkg_version("docling-parse"),
        # base version only: "2.14.1+cpu" (laptop) and "2.14.1+cu128" (box) must match
        "torch": _pkg_version("torch").split("+")[0],
        "min_chunk_words": min_chunk_words,
        "content_start_page": content_start_page,
        "metadata": metadata,
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class ParseJob:
    """
    One doc to parse: `source_url` keys its cache entry (and Chroma chunks), `source` is
    what `parse_with_docling` reads (local path or http url).

    Purpose: shared by the stale-chunk migration (laptop, from Postgres) and the
    parse-only worker (box, from the manifest), so both compute the same fingerprint.
    """
    source_url: str
    label: str
    source: str
    metadata: dict[str, Any]
    min_chunk_words: int | None = None
    content_start_page: int = 1

    def fingerprint(self) -> str:
        return parse_fingerprint(self.metadata, min_chunk_words=self.min_chunk_words,
                                 content_start_page=self.content_start_page)

    def parse(self) -> list[dict[str, Any]]:
        return parse_with_docling(self.source, self.metadata,
                                  min_chunk_words=self.min_chunk_words,
                                  content_start_page=self.content_start_page)


def cache_path(cache_dir: Path, source_url: str) -> Path:
    return cache_dir / f"{hashlib.md5(source_url.encode()).hexdigest()}.json"


def load_cached_chunks(cache_dir: Path, source_url: str,
                       fingerprint: str) -> list[dict[str, Any]] | None:
    """Cached chunks for `source_url`, or None if missing, unreadable or stale."""
    path = cache_path(cache_dir, source_url)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        log.warning(f"   → unreadable cache entry {path.name}: {e}")
        return None
    if entry.get("source_url") != source_url or entry.get("fingerprint") != fingerprint:
        return None
    return entry["chunks"]


def load_cache_env(cache_dir: Path, source_url: str) -> str:
    """`parse_env` of a cache entry as a short label, for the dry run's mix check."""
    entry = json.loads(cache_path(cache_dir, source_url).read_text())
    env = entry.get("parse_env")
    return f"{env['torch']} on {env['device']}" if env else "unknown (pre-#80 entry)"


def save_cached_chunks(cache_dir: Path, source_url: str, label: str, fingerprint: str,
                       chunks: list[dict[str, Any]]) -> None:
    """Atomic write (tmp + rename) so an interrupted run never leaves a half entry."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, source_url)
    entry = {"source_url": source_url, "label": label, "fingerprint": fingerprint,
             "parse_env": parse_env(), "chunks": chunks}
    _write_atomic(path, json.dumps(entry, ensure_ascii=False, default=str))


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


@dataclass(frozen=True)
class ParseFailure:
    """
    A doc the parse box couldn't parse (#77): `reason` is `oom_killed`, `signal`,
    `exit:<code>` or `exception:<type>`.
    """
    source_url: str
    label: str
    reason: str
    detail: str
    exit_signal: int | None
    last_rss_mb: int | None
    fingerprint: str


def load_failures(cache_dir: Path) -> dict[str, ParseFailure]:
    """Current failures by source_url (empty if the box never wrote any)."""
    path = cache_dir / FAILED_FILE
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {row["source_url"]: ParseFailure(**row) for row in rows}


def save_failures(cache_dir: Path, failures: dict[str, ParseFailure]) -> None:
    """
    Rewrite failed.jsonl atomically. Rewritten rather than appended, so a later success
    clears a doc's failure.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(asdict(f), ensure_ascii=False) for f in failures.values())
    _write_atomic(cache_dir / FAILED_FILE, "".join(f"{line}\n" for line in lines))
