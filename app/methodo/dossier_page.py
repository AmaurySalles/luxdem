"""
Reads the facts CHD open data lacks from a dossier's chd.lu page (#119): commissions,
rapporteurs and vote bulletin links.
"""
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

_TIMEOUT_S = 30
_BULLETIN_MARK = "Bulletin"
_COMMISSION_HEADINGS = {"Commission", "Commissions"}


@dataclass(frozen=True)
class DossierPageFacts:
    commission_titles: list[str]
    rapporteur_names: list[str]
    bulletin_urls: list[str]


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
    )


def scrape_dossier_page(url: str) -> DossierPageFacts:
    """Facts from one dossier page. TLS stays verified (system CA bundle, see DECISIONS)."""
    response = requests.get(url, timeout=_TIMEOUT_S)
    response.raise_for_status()
    return parse_dossier_page(response.text)
