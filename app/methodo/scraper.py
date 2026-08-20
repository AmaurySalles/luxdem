"""
Standalone scraper for all legislative dossiers from chd.lu.

Features:
- Fetch ALL dossier URLs across all pages via pagination.
- Parse individual dossier detail pages for metadata.
- Support for both AJAX and direct HTML parsing.
- During For Loop:
    SleepTimer of several seconds to avoid denial of service event

Usage:
    # Fetch all dossiers:
    python app/db_model/insertors/scraper.py

    # Parse a specific dossier:
    python app/db_model/insertors/scraper.py https://www.chd.lu/fr/dossier/8695
"""
from ecodev_core import logger_get
import datetime
import json
import time
from typing import List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from sqlmodel import Session, select

from app.db_model import Resource
from app.db_model.tables.dossier import Dossier
from app.domain_model import DossierStatus
from app.db_model.inserters.dossier_inserters import upsert_dossier

log = logger_get(__name__)

# Choose parser: prefer lxml if installed, fall back to Python's built-in parser.
try:
    import lxml  # type: ignore
    PARSER = "lxml"
except Exception:
    PARSER = "html.parser"


BASE_URL = "https://www.chd.lu"
SEARCH_PATH = "/fr/searchfolders"


def scrape_chd_lu_for_dossiers(session: Session, start: int = 8_000, max_consecutive_misses: int = 20) -> list[dict[str, Exception]]:
    """
    Scrape dossier detail pages from chd.lu starting at `start`.
    Stops automatically after `max_consecutive_misses` consecutive missing dossiers,
    which indicates the end of existing dossiers has been reached.
    """
    summary = []
    consecutive_misses = 0
    dossier_number = start

    while True:
        time.sleep(0.1)
        url = urljoin(BASE_URL, f"/fr/dossier/{dossier_number}")
        try:
            if session.exec(select(Dossier).where(Dossier.number == str(dossier_number))).first():
                log.debug(f'Skipping dossier #{dossier_number} (already in DB)')
                consecutive_misses = 0
                dossier_number += 1
                continue
            log.info(f'Retrieving dossier #{dossier_number}')
            if (dossier := scrape_dossier(url)) is not None:
                upsert_dossier(session, dossier)
                summary.append({dossier_number: {"status": 'success', "url": url, "error": None}})
                consecutive_misses = 0
            else:
                consecutive_misses += 1
                if consecutive_misses >= max_consecutive_misses:
                    log.info(f"Stopping after {max_consecutive_misses} consecutive missing dossiers at #{dossier_number}")
                    break
        except Exception as error:
            summary.append({dossier_number: {"status": 'failed', "url": url, "error": error}})
            consecutive_misses += 1
            if consecutive_misses >= max_consecutive_misses:
                log.info(f"Stopping after {max_consecutive_misses} consecutive errors at #{dossier_number}")
                break

        dossier_number += 1

    return summary


def scrape_dossier(url: str) -> Dossier | None:
    """Scrape a dossier detail page and extract required fields.

    Returns a dict with keys:
      law_number, law_type, law_deposit_date, law_evacuation_date,
      law_status, law_title, law_content, law_authors, source_url
    """
    try:
        session = requests.Session()
        r = session.get(url, timeout=30, verify=False)
        soup = BeautifulSoup(r.text, PARSER)
        if not (body := soup.find(id="main-content")):
            log.error(f"No main content found for URL: {url}")
            return None

        if not (dossier_number := text_of(body, ".chd-pageTitleHeader__title")):
            log.error(f"No dossier number found for URL: {url}")
            return None

        right_info_column = find_right_info_column(body)
        activities = find_activities(body)

        return Dossier(
            number=int(dossier_number),
            title=text_of(body, ".chd-wysiwyg.text-large"),

            type=get_description_list_info("Type", right_info_column),
            status=find_dossier_status(right_info_column),

            deposit_date=find_dossier_deposit_date(right_info_column),
            evacuation_date=None,
            
            content=None,
            authors=get_description_list_info("Auteur", right_info_column),
            resources=find_doc_download_url(soup)
        )
    
    except Exception as e:
        log.error(f"Error parsing dossier {url}: {e}")
        return None


def text_of(soup: BeautifulSoup, selector: str) -> str | None:
    el = soup.select_one(selector)
    if not el:
        return None
    return " ".join(el.get_text(strip=True).split())


def get_description_list_info(key: str, soup: BeautifulSoup) -> str | None:
    """
    Accesses the description list on the right of the page, and returns the value for the field key provided
    """
    for dt in soup.select("dl dt"):
        if dt.get_text(strip=True).startswith(key):
            dd = dt.find_next_sibling("dd")
            if dd:
                return dd.get_text(strip=True)
    return None


def convert_date_to_datetime(date_str: str) -> datetime.datetime | None:
    """
    Converts a date string in 'dd/mm/yyyy' format to a datetime.datetime object.
    """
    if date_str == "nan":
        return None
    return datetime.datetime.strptime(date_str, "%d.%m.%Y")


def find_right_info_column(soup: BeautifulSoup) -> BeautifulSoup:
    return soup.find("div", class_="right-column")


def find_published_badge(soup: BeautifulSoup) -> List[str]:
    """
    Finds all badges in the page and returns a list of their text.
    """
    return DossierStatus.Publie if soup.find_all("span", class_="badge badge-validated mr-8") else None


def find_dossier_status(soup: BeautifulSoup) -> DossierStatus | None:
    """
    Finds the dossier status in the page and returns it.
    """
    if law_status := get_description_list_info("Statut", soup):
        return DossierStatus(law_status)
    if published_badge := find_published_badge(soup):
        return DossierStatus.Publie
    return None

def find_dossier_deposit_date(soup: BeautifulSoup) -> datetime.datetime | None:
    """
    Finds the dossier deposit date in the page and returns it.
    """
    return convert_date_to_datetime(get_description_list_info("Date de dépôt", soup))


def find_activities(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Finds the activities in the page and returns them.
    """
    return soup.find('div', id='scrolltab-section-3')


def find_doc_download_url(soup: BeautifulSoup) -> str | None:
    """
    Finds the document download URL in the page and returns it.
    """
    seen_urls = set()
    resources = []
    for link in soup.find_all('a', class_='chd-iconLinkBlock'):
        url = link.get('href')
        if url and url not in seen_urls:
            seen_urls.add(url)
            resources.append(Resource(
                title=link.get_text(strip=True),
                url=url,
            ))
    return resources






# def fetch_all_dossier_urls(page_size: int = 10, timeout: int = 15) -> List[str]:
#     """Fetch ALL dossier detail URLs across all pages via pagination.

#     Iterates through all pages of search results using iStart/iSize parameters,
#     collecting unique dossier URLs until no new links are found.

#     Returns a sorted list of absolute URLs.
#     """
#     all_hrefs = set() # Set does not allow for duplicates #
#     session = requests.Session()
#     i_start = 0

#     while i_start < 10:
#         REQUEST_DELAY_SECONDS = 1
#         time.sleep(REQUEST_DELAY_SECONDS)  # One request → wait 1 seconds → next request = much lower risk of getting blocked

#         # Try AJAX wrapper first
#         ajax_url = urljoin(BASE_URL, SEARCH_PATH) + "?_wrapper_format=drupal_ajax"
#         payload = {
#             "searchTerm": "ALL",
#             "searchAuteur": "",
#             "searchDestinataire": "",
#             "searchCommision": "",
#             "filterType": "Dossiers Législatifs",
#             "filterSubtype": "",
#             "status": "",
#             "order": "DATE_DESC",
#             "TypeDate": "MODIFICATION",
#             "dDateF": "",
#             "dDateT": "",
#             "iStart": str(i_start),
#             "iSize": str(page_size),
#         }

#         try:
#             r = session.post(ajax_url, data=payload, timeout=timeout)
#             text = r.text.strip()
#             # Drupal AJAX returns a JSON array of commands; try to parse and extract HTML
#             if text.startswith("["):
#                 data = json.loads(text)
#                 html_parts = []
#                 for item in data:
#                     if isinstance(item, dict) and "data" in item:
#                         html_parts.append(item.get("data") or "")
#                 combined = "\n".join(html_parts)
#                 soup = BeautifulSoup(combined, PARSER)
#             else:
#                 # Fallback: parse the response body as HTML
#                 soup = BeautifulSoup(text, PARSER)
#         except Exception:
#             # Final fallback: GET the normal search page with query params
#             params = {
#                 "searchTerm": "ALL",
#                 "filterType": "Dossiers Législatifs",
#                 "iStart": str(i_start),
#                 "iSize": str(page_size),
#                 "order": "DATE_DESC",
#                 "TypeDate": "MODIFICATION",
#             }
#             r = session.get(urljoin(BASE_URL, SEARCH_PATH), params=params, timeout=timeout)
#             soup = BeautifulSoup(r.text, PARSER)

#         # Collect candidate links from this page
#         page_hrefs = set()
#         for a in soup.find_all("a", href=True):
#             href = a["href"].strip()
#             # ignore anchors and links to the search page itself
#             if href.startswith("#"):
#                 continue
#             # some links are absolute already
#             if href.startswith(BASE_URL):
#                 full = href
#             else:
#                 full = urljoin(BASE_URL, href)

#             # Only keep real dossier-like pages (tight and explicit)
#             parsed = urlparse(full)
#             if parsed.netloc == "www.chd.lu" and parsed.path.startswith((
#                 "/fr/dossier/",
#                 "/fr/texte-de-loi/",
#             )):
#                 page_hrefs.add(full)


#         # If no new links found on this page, we're done
#         if not page_hrefs or page_hrefs.issubset(all_hrefs):
#             break

#         all_hrefs.update(page_hrefs)
#         i_start += page_size

#     # Return sorted list
#     return sorted(all_hrefs)



# def main() -> None:

#     # Default behavior: fetch ALL dossier links from all pages.
#     print("Fetching all dossier URLs from chd.lu (this may take a moment)...")
#     links = fetch_all_dossier_urls(page_size=10)
#     if links:
#         print(f"\nFound {len(links)} total dossier detail links:")
#         for u in links:
#             print(u)
#     else:
#         print("No dossier links found — parsing example dossier /fr/dossier/8695")
#         data = parse_dossier(urljoin(BASE_URL, "/fr/dossier/8695"))
#         print(json.dumps(data, ensure_ascii=False, indent=2))


