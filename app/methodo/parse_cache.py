"""
On-disk cache of Docling parse results, so parsing (slow, free on the laptop) and
embedding (needs the rented GPU) can run as separate passes (#46).

One JSON file per doc: `<cache_dir>/<md5(source_url)>.json` holding `source_url`,
`label`, `fingerprint` and `chunks` (the exact `parse_with_docling` output).

A cache entry is only valid if its fingerprint matches the current one, which hashes
the `docling_parser.py` source (chunker/tokenizer settings live there), the installed
docling + docling-core versions, the parse args (`min_chunk_words`,
`content_start_page`) and the doc's DB metadata. Any of these changing invalidates the
entry, so a parser change between the parse and embed passes can't slip through.
"""
import hashlib
import json
import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ecodev_core import logger_get

from app.constants import DATA_DIR

log = logger_get(__name__)

PARSE_CACHE_DIR = DATA_DIR / "parse_cache"
_PARSER_SOURCE = Path(__file__).parent / "parsing" / "docling_parser.py"


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"


def parse_fingerprint(metadata: dict[str, Any],
                      min_chunk_words: int | None = None,
                      content_start_page: int = 1) -> str:
    """Hash of everything that determines `parse_with_docling`'s output for one doc."""
    parts = {
        "parser_source": hashlib.sha256(_PARSER_SOURCE.read_bytes()).hexdigest(),
        "docling": _pkg_version("docling"),
        "docling_core": _pkg_version("docling-core"),
        "min_chunk_words": min_chunk_words,
        "content_start_page": content_start_page,
        "metadata": metadata,
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


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


def save_cached_chunks(cache_dir: Path, source_url: str, label: str, fingerprint: str,
                       chunks: list[dict[str, Any]]) -> None:
    """Atomic write (tmp + rename) so an interrupted run never leaves a half entry."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, source_url)
    tmp = path.with_suffix(".tmp")
    entry = {"source_url": source_url, "label": label, "fingerprint": fingerprint,
             "chunks": chunks}
    tmp.write_text(json.dumps(entry, ensure_ascii=False, default=str))
    os.replace(tmp, path)
