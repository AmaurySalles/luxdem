"""
Manifest of every doc the parse box parses (#71, #80): one JSON line per doc, exported
on the laptop from Postgres, read on the box (which has no Postgres or Chroma).

Each row is a `ParseJob` whose `file` is relative to the data dir, plus the doc's
`page_count` (routes docs over 250 pages to the long lane, #77). The DB metadata rides
along, so the box computes the same fingerprints as the laptop dry run.
"""
import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2
from sqlmodel import Session

from app.constants import DATA_DIR
from app.methodo.onh_pipeline import COALITION_PDF
from app.methodo.onh_pipeline import coalition_parse_job
from app.methodo.parse_cache import ParseJob
from app.methodo.stale_chunk_migration import collect_targets

PILOT_A_DOSSIER_DIR = DATA_DIR / "_pilot_a" / "all"


@dataclass(frozen=True)
class ManifestRow:
    """One doc to parse on the box: `file` is relative to the box's data dir."""
    source_url: str
    label: str
    file: str
    metadata: dict[str, Any]
    min_chunk_words: int | None
    content_start_page: int
    page_count: int

    def to_job(self, data_dir: Path) -> ParseJob:
        return ParseJob(source_url=self.source_url, label=self.label,
                        source=str(data_dir / self.file), metadata=self.metadata,
                        min_chunk_words=self.min_chunk_words,
                        content_start_page=self.content_start_page)


class ManifestFilesMissingError(Exception):
    """Docs whose PDF isn't under the data dir: the box would have nothing to parse."""

    def __init__(self, missing: list[tuple[str, str]]) -> None:
        self.missing = missing  # (label, expected path)
        lines = "\n".join(f"  {label}: {path}" for label, path in missing)
        super().__init__(f"{len(missing)} doc(s) have no local PDF:\n{lines}")


def _to_row(job: ParseJob, data_dir: Path) -> ManifestRow:
    path = Path(job.source)
    with pypdfium2.PdfDocument(path) as pdf:
        page_count = len(pdf)
    return ManifestRow(source_url=job.source_url, label=job.label,
                       file=path.resolve().relative_to(data_dir.resolve()).as_posix(),
                       metadata=job.metadata, min_chunk_words=job.min_chunk_words,
                       content_start_page=job.content_start_page, page_count=page_count)


def build_manifest(session: Session,
                   dossier_dir: Path = PILOT_A_DOSSIER_DIR,
                   coalition_pdf: Path = COALITION_PDF,
                   data_dir: Path = DATA_DIR) -> list[ManifestRow]:
    """
    Rows for every ONH + dossier doc (as the stale-chunk migration sees them) and the
    coalition agreement.

    Raises:
        ManifestFilesMissingError: a doc's PDF is missing or not under `data_dir`, so the
            box (which rsyncs `data_dir` and never downloads) couldn't parse it.
    """
    jobs = [*collect_targets(session, dossier_dir=dossier_dir),
            coalition_parse_job(coalition_pdf)]
    data_root = data_dir.resolve()
    missing = [(job.label, job.source) for job in jobs
               if not Path(job.source).is_file()
               or not Path(job.source).resolve().is_relative_to(data_root)]
    if missing:
        raise ManifestFilesMissingError(missing)
    return [_to_row(job, data_dir) for job in jobs]


def write_manifest(rows: list[ManifestRow], path: Path) -> None:
    """
    NOTE: `default=str` (dates in dossier metadata) matches `parse_fingerprint`'s own
    serialization, so the box computes the same fingerprints from the strings.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n"
                            for r in rows))


def read_manifest(path: Path) -> list[ManifestRow]:
    return [ManifestRow(**json.loads(line))
            for line in path.read_text().splitlines() if line.strip()]
