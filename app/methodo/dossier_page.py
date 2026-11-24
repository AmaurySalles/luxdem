"""
Reads the facts CHD open data lacks from a dossier's chd.lu page (#119): commissions,
rapporteurs, vote bulletin links and the dated activities of the procedure.
"""
from dataclasses import dataclass
from datetime import date
from datetime import datetime

import requests
from bs4 import BeautifulSoup

_TIMEOUT_S = 30
_BULLETIN_MARK = "Bulletin"
_COMMISSION_HEADINGS = {"Commission", "Commissions"}
_TOGGLE_TEXT = " Bouton graphique servant à afficher"  # a collapsible list's button label


@dataclass(frozen=True)
class Activity:
    day: date
    description: str
    actor: str


@dataclass(frozen=True)
class DossierPageFacts:
    commission_titles: list[str]
    rapporteur_names: list[str]
    bulletin_urls: list[str]
    activities: list[Activity]


def _activities(soup: BeautifulSoup) -> list[Activity]:
    """
    Rows of the 'Date | Description | Intervenant' table, oldest first.

    NOTE: the page renders the table twice (two layouts); the first is read.
    """
    table = next((t for t in soup.select("table")
                  if [th.get_text(strip=True) for th in t.select("th")][:3]
                  == ["Date", "Description", "Intervenant"]), None)
    if table is None:
        return []
    activities = []
    for row in table.select("tbody > tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split())
                 for td in row.find_all("td", recursive=False)]
        if len(cells) >= 3 and cells[1]:
            day = datetime.strptime(cells[0], "%d.%m.%Y").date()
            activities.append(Activity(day, cells[1].split(_TOGGLE_TEXT)[0], cells[2]))
    return sorted(activities, key=lambda a: a.day)


def _rapporteur_names(soup: BeautifulSoup) -> list[str]:
    for dt in soup.select("dl dt"):
        if dt.get_text(strip=True) == "Rapporteur" and (dd := dt.find_next_sibling("dd")):
            return [a.get_text(strip=True) for a in dd.select("a")]
    return []


def _commission_titles(soup: BeautifulSoup, rapporteurs: list[str]) -> list[str]:
    """
    Commission links of the 'Commission(s)' block.

    NOTE: chd.lu also renders the rapporteur there as a commission link ('Franz Fayot'),
    so names listed as rapporteur are dropped.
    """
    heading = next((d for d in soup.select("div.font-weight-bold")
                    if d.get_text(strip=True) in _COMMISSION_HEADINGS), None)
    block = heading.find_next_sibling("dl") if heading else None
    if block is None:
        return []
    titles = [a.get_text(strip=True) for a in block.select('a[href^="/fr/commission/"]')]
    return list(dict.fromkeys(t for t in titles if t not in rapporteurs))


def parse_dossier_page(html: str) -> DossierPageFacts:
    soup = BeautifulSoup(html, "html.parser")
    rapporteurs = _rapporteur_names(soup)
    bulletins = [a["href"] for a in soup.select("a[href]")
                 if _BULLETIN_MARK in a["href"] and a["href"].lower().endswith(".pdf")]
    return DossierPageFacts(
        commission_titles=_commission_titles(soup, rapporteurs),
        rapporteur_names=rapporteurs,
        bulletin_urls=list(dict.fromkeys(bulletins)),
        activities=_activities(soup),
    )


def scrape_dossier_page(url: str) -> DossierPageFacts:
    """Facts from one dossier page. TLS stays verified (system CA bundle, see DECISIONS)."""
    response = requests.get(url, timeout=_TIMEOUT_S)
    response.raise_for_status()
    return parse_dossier_page(response.text)
