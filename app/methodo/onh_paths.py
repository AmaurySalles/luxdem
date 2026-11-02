"""
ONH sources are stored relative to `DATA_DIR / "downloads"`, e.g. `onh/Note-30.pdf`, in
`OnhPublication.url` and as the chunks' `source_url` (#49). They are resolved at parse
time, so the same DB value works in Docker and natively (`base_path`-aware DATA_DIR).
"""
from dataclasses import dataclass
from pathlib import Path

from app.constants import DATA_DIR
from app.db_model.tables.onh_publication import OnhPublication

DOWNLOADS_DIR = DATA_DIR / "downloads"
ONH_DOWNLOADS_DIR = DOWNLOADS_DIR / "onh"
_FILE_PREFIX = "file://"


def resolve_onh_source(url: str, onh_dir: Path | None = None) -> str:
    """
    Local path (or http url) to parse for a stored ONH url. Relative values resolve under
    DOWNLOADS_DIR; legacy `file://` values are used as-is if present, else looked up by
    file name under ONH_DOWNLOADS_DIR. `onh_dir` is a fallback when neither exists.
    """
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith(_FILE_PREFIX):
        path = Path(url.removeprefix(_FILE_PREFIX))
        if not path.exists():
            path = ONH_DOWNLOADS_DIR / path.name
    else:
        path = DOWNLOADS_DIR / url
    if onh_dir is not None and not path.exists():
        path = Path(onh_dir) / path.name
    return str(path)


def relative_to_downloads(pdf_path: Path) -> str:
    """Stored (posix) form of a local path. Raises ValueError if it is outside DOWNLOADS_DIR."""
    return Path(pdf_path).resolve().relative_to(DOWNLOADS_DIR.resolve()).as_posix()


@dataclass
class OnhUrlRewrite:
    id: int
    old_url: str
    new_url: str
    file_found: bool


def plan_onh_url_rewrites(publications: list[OnhPublication]) -> list[OnhUrlRewrite]:
    """Legacy `file://.../<file>` urls -> `onh/<file>`. Already-relative / http urls skipped."""
    rewrites = []
    for pub in publications:
        if pub.id is None or not pub.url.startswith(_FILE_PREFIX):
            continue
        local = ONH_DOWNLOADS_DIR / Path(pub.url.removeprefix(_FILE_PREFIX)).name
        rewrites.append(OnhUrlRewrite(id=pub.id, old_url=pub.url,
                                      new_url=local.relative_to(DOWNLOADS_DIR).as_posix(),
                                      file_found=local.is_file()))
    return rewrites
