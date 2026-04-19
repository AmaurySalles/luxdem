"""
Scraper for Observatoire National de l'Habitat (ONH) publications.
Source: https://logement.public.lu/fr/observatoire-habitat/publications.html

Falls back to manual import if the site blocks automated access.
"""
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from ecodev_core import logger_get
from sqlmodel import Session

from app.db_model.tables.onh_publication import OntPublication
from app.db_model.retrievers.onh_retriever import upsert_onh_publication

log = logger_get(__name__)

ONH_BASE = "https://logement.public.lu"
ONH_PUBLICATIONS_PATH = "/fr/observatoire-habitat/publications.html"
ONH_DOWNLOADS_DIR = Path("downloads/onh")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-LU,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://logement.public.lu/",
}


def scrape_onh_publications(session: Session) -> list[OntPublication]:
    """Scrape ONH publication index and persist metadata to DB."""
    listing_url = urljoin(ONH_BASE, ONH_PUBLICATIONS_PATH)
    log.info(f"Scraping ONH publications from {listing_url}")

    try:
        resp = requests.get(listing_url, headers=BROWSER_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.HTTPError as e:
        log.error(f"Failed to fetch ONH listing (HTTP {e.response.status_code}). "
                  "Use ingest_onh_pdfs_from_dir() for manual import.")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    publications = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.lower().endswith(".pdf"):
            continue

        pdf_url = href if href.startswith("http") else urljoin(ONH_BASE, href)
        title = link.get_text(strip=True) or Path(href).stem

        pub = OntPublication(
            title=title,
            url=pdf_url,
            listing_url=listing_url,
            category=_infer_category(title),
        )
        persisted = upsert_onh_publication(session, pub)
        publications.append(persisted)
        time.sleep(0.1)

    log.info(f"Found {len(publications)} ONH publications")
    return publications


def ingest_onh_pdfs_from_dir(session: Session, pdf_dir: Path) -> list[OntPublication]:
    """Manual fallback: ingest PDFs placed in pdf_dir by the user."""
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        log.error(f"Directory not found: {pdf_dir}")
        return []

    publications = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        pub = OntPublication(
            title=pdf_path.stem.replace("_", " ").replace("-", " "),
            url=pdf_path.as_uri(),
            listing_url=str(pdf_dir),
            category=_infer_category(pdf_path.stem),
        )
        persisted = upsert_onh_publication(session, pub)
        publications.append(persisted)

    log.info(f"Ingested {len(publications)} ONH PDFs from {pdf_dir}")
    return publications


def _infer_category(title: str) -> str:
    title_lower = title.lower()
    if "note" in title_lower:
        return "note"
    if "rapport" in title_lower or "annual" in title_lower:
        return "rapport"
    return "etude"
