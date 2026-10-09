# === Step 1: Download PDF ===
import hashlib
from pathlib import Path

import requests
from ecodev_core import logger_get
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logger_get(__name__)

# === Configuration ===
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# (connect, read) seconds. Docling's own URL fetch sets no timeout and can hang
# indefinitely on a stalled chd.lu connection, so remote PDFs go through here instead.
_TIMEOUT = (10, 60)
# Few, quick retries for transient 5xx / connection resets. SSL verification errors are
# not retried: a bad cert won't fix itself, so fail fast with the real error.
_RETRY = Retry(total=2, connect=2, read=2, status=2, other=0, backoff_factor=1,
               status_forcelist=(500, 502, 503, 504), allowed_methods=("GET",))


def _session() -> requests.Session:
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=_RETRY))
    session.mount("http://", HTTPAdapter(max_retries=_RETRY))
    return session


def download_pdf(pdf_url: str) -> Path:
    """Download PDF from URL and save locally (cached). Raises on any fetch/TLS error.

    TLS verification uses certifi by default; set REQUESTS_CA_BUNDLE to point at another
    CA bundle if an environment needs one.
    """
    # url hash prefix: chd.lu basenames aren't guaranteed unique across dossiers
    url_hash = hashlib.md5(pdf_url.encode()).hexdigest()[:8]
    dest = DOWNLOADS_DIR / f"{url_hash}_{pdf_url.rstrip('/').split('/')[-1]}"

    if dest.exists():
        log.info(f"   → PDF already downloaded: {dest}")
        return dest

    log.info(f"   → Downloading {pdf_url}...")
    with _session() as session:
        response = session.get(pdf_url, timeout=_TIMEOUT)
    response.raise_for_status()
    # write-then-rename so an interrupted download never leaves a truncated cached file
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(response.content)
    tmp.rename(dest)
    log.info(f"   → Saved to {dest}")
    return dest
