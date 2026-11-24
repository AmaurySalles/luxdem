"""
Government members from gouvernement.lu (#119): who held which ministry when, and the party
their biography states.

- Mandates: the 'Anciens membres du gouvernement' page lists every function of every member
  since 1999 with its dates, current members included ('depuis le 17.11.2023').
- Party: only biographies that state it ('Membre du DP depuis 1994'); others stay unknown
  here, and deputies' parties come from CHD open data instead.
"""
import re
import time
from dataclasses import dataclass
from datetime import date

import requests
from bs4 import BeautifulSoup
from ecodev_core import logger_get
from sqlmodel import Session

from app.db_model.inserters.government_inserters import replace_government
from app.db_model.tables.government import GovernmentMandate
from app.db_model.tables.government import PartyStatement

log = logger_get(__name__)

GOVERNMENT_URL = "https://gouvernement.lu/fr/gouvernement.html"
MANDATES_URL = "https://gouvernement.lu/fr/gouvernement/anciens-membres-gouvernement.html"
_TIMEOUT_S = 30
_DELAY_S = 0.5
_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
           "octobre", "novembre", "décembre"]
# '17.11.2023' or '17 novembre 2023'
_DATE = rf"\d{{1,2}}(?:\.\d{{2}}\.| (?:{'|'.join(_MONTHS)}) )\d{{4}}"
# 'Ministre X, du 05.01.2022 au 16.11.2023', 'Ministre X depuis le 17.11.2023',
# 'Ministre X le 17.11.2023' (in office), 'Ministre X du 17 novembre 2023 au 11 décembre 2025'
_MANDATE = re.compile(rf"^(?P<function>.+?),? (?:du (?P<start>{_DATE}) au (?P<end>{_DATE})"
                      rf"|(?:depuis )?le (?P<since>{_DATE}))$")
# Party names as biographies write them, mapped to CHD open data abbreviations
_PARTIES = {"DP": "DP", "Parti démocratique": "DP", "CSV": "CSV", "Parti chrétien-social": "CSV",
            "LSAP": "LSAP", "Parti ouvrier socialiste luxembourgeois": "LSAP",
            "déi gréng": "déi gréng"}
_PARTY_NAMES = "|".join(sorted(map(re.escape, _PARTIES), key=len, reverse=True))
_MEMBERSHIP = re.compile(rf"(?:Membre|membre) du (?:parti )?(?P<party>{_PARTY_NAMES})"
                         rf"(?: \([A-Z]+\))?(?: depuis \d{{4}})?")


class GovernmentFormatError(Exception):
    """A gouvernement.lu page does not have the layout this parser reads."""

    def __init__(self, url: str, detail: str) -> None:
        super().__init__(f"{url}: {detail}")
        self.url = url
        self.detail = detail


@dataclass(frozen=True)
class ParsedMandate:
    last_name: str
    first_name: str
    function: str
    start: date
    end: date | None


def _to_date(text: str) -> date:
    day, month, year = re.split(r"[. ]", text)
    month_number = int(month) if month.isdigit() else _MONTHS.index(month) + 1
    return date(int(year), month_number, int(day))


def split_listed_name(listed: str) -> tuple[str, str]:
    """('BACKES', 'Yuriko') from 'BACKES Yuriko'; last names are upper case, maybe several words."""
    words = listed.split()
    last = [w for w in words if w.isupper() and len(w) > 1]
    first = [w for w in words if w not in last]
    return " ".join(last).title(), " ".join(first)


def parse_mandates(html: str) -> list[ParsedMandate]:
    """Every mandate on the former members page: one accordion per person, one item per function."""
    mandates = []
    for person in BeautifulSoup(html, "html.parser").select("details.cmp-accordion__item"):
        header = person.select_one("h3")
        if header is None:
            continue
        last, first = split_listed_name(header.get_text(" ", strip=True))
        for item in person.select("li"):
            text = " ".join(item.get_text(" ", strip=True).split())
            if not (match := _MANDATE.match(text)):
                raise GovernmentFormatError(MANDATES_URL, f"unreadable mandate {text!r}")
            mandates.append(ParsedMandate(
                last, first, match["function"], _to_date(match["start"] or match["since"]),
                _to_date(match["end"]) if match["end"] else None))
    if not mandates:
        raise GovernmentFormatError(MANDATES_URL, "no mandates")
    return mandates


def parse_party_statement(biography_text: str) -> tuple[str, str] | None:
    """(party abbreviation, quote) when the biography states membership of a party."""
    if match := _MEMBERSHIP.search(" ".join(biography_text.split())):
        return _PARTIES[match["party"]], match[0]
    return None


def _get(url: str) -> str:
    response = requests.get(url, timeout=_TIMEOUT_S)
    response.raise_for_status()
    return response.text


def _biography_urls() -> dict[tuple[str, str], str]:
    """Biography url per (last, first) of the current members."""
    soup = BeautifulSoup(_get(GOVERNMENT_URL), "html.parser")
    urls = {}
    for link in soup.select("li.subnav-item a[href*='/fr/gouvernement/']"):
        if "anciens-membres" in link["href"]:
            continue
        first_last = link.get_text(" ", strip=True)  # 'Claude MEISCH'
        last, first = split_listed_name(first_last)
        urls[(last, first)] = "https:" + link["href"].replace(".html", "/biographie.html")
    return urls


def import_government(session: Session) -> tuple[int, int]:
    """
    Scrape and store all mandates and the current members' party statements.

    Returns:
        Number of mandates and of party statements stored.
    """
    biographies = _biography_urls()
    parsed = parse_mandates(_get(MANDATES_URL))
    # The page has open mandates of people no longer in government (Mutsch, 'depuis le
    # 18.12.2015'): their end is unknown, so they are left out rather than shown as current.
    stale = [m for m in parsed if m.end is None and (m.last_name, m.first_name) not in biographies]
    for mandate in stale:
        log.warning(f"Open mandate of a former member left out: {mandate}")
    mandates = [GovernmentMandate(last_name=m.last_name, first_name=m.first_name,
                                  function=m.function, start=m.start, end=m.end,
                                  source_url=MANDATES_URL)
                for m in parsed if m not in stale]
    statements = []
    for (last, first), url in biographies.items():
        time.sleep(_DELAY_S)
        text = BeautifulSoup(_get(url), "html.parser").get_text(" ", strip=True)
        if (found := parse_party_statement(text)) is None:
            log.info(f"No party stated in {url}")
            continue
        party, quote = found
        statements.append(PartyStatement(last_name=last, first_name=first, party=party,
                                         quote=quote, source_url=url))
    replace_government(session, mandates, statements)
    return len(mandates), len(statements)
