"""
Parses CHD 'Bulletin de Vote (Vote Public)' PDFs (#119): the only public source naming whose
vote each proxy seat was ('Arendt Nancy Oui (Adehm Diane)': Adehm cast Arendt's vote).
"""
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pypdfium2 as pdfium

from app.domain_model.ballot import VoteChoice

_CHD_TZ = ZoneInfo("Europe/Luxembourg")
# Layouts: 'Date: 15/07/2026 19:51:11' / 'Vote: PL 8727 - ...' until Oct 2026, then
# 'Date : 29/10/2026 - 19:53:01' / 'Objet vote : Projet de loi N°8725'
_DATE = re.compile(r"^Date ?: (\d{2}/\d{2}/\d{4})(?: -)? (\d{2}:\d{2}:\d{2})", re.M)
_LABEL = re.compile(r"^(?:Vote|Objet vote) ?: (.+?)(?: Secrétaire .*)?$", re.M)
_BODY_START = re.compile(r"^Total:.*$", re.M)  # vote totals row, printed on every page
_BODY_END = re.compile(r"n'ont pas participé au vote|Le Président:")
_ENTRY = re.compile(r"\s*(?P<name>.+?) (?P<choice>Oui|Non|Abst)(?: \((?P<holder>[^)]+)\))?(?=\s|$)")
_CHOICES = {"Oui": VoteChoice.Oui, "Non": VoteChoice.Non, "Abst": VoteChoice.Abstention}


class BulletinFormatError(Exception):
    """A bulletin does not have the layout this parser reads."""

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"{source}: {detail}")
        self.source = source
        self.detail = detail


@dataclass(frozen=True)
class BulletinEntry:
    deputy_name: str
    choice: VoteChoice
    proxy_holder_name: str | None  # who cast this vote, when the deputy was absent


@dataclass(frozen=True)
class Bulletin:
    held_at: datetime
    label: str
    entries: list[BulletinEntry]


def _body_lines(page_text: str) -> list[str]:
    start = _BODY_START.search(page_text)
    if start is None:
        return []
    body = page_text[start.end():]
    if end := _BODY_END.search(body):
        body = body[:end.start()]
    return body.splitlines()


def parse_bulletin_text(pages: list[str], source: str) -> Bulletin:
    """
    Bulletin from the text of its pages. Party headings and non-participants are skipped:
    a non-participant casts no proxy, so their seat needs no resolving.
    """
    date, label = _DATE.search(pages[0]), _LABEL.search(pages[0])
    if not (date and label):
        raise BulletinFormatError(source, "no Date/Vote header")
    entries = [BulletinEntry(m["name"].strip(), _CHOICES[m["choice"]], m["holder"])
               for page in pages for line in _body_lines(page) for m in _ENTRY.finditer(line)]
    if not entries:
        raise BulletinFormatError(source, "no vote lines")
    return Bulletin(
        held_at=datetime.strptime(f"{date[1]} {date[2]}", "%d/%m/%Y %H:%M:%S")
        .replace(tzinfo=_CHD_TZ),
        label=label[1].strip(),
        entries=entries,
    )


def read_bulletin(path: Path) -> Bulletin:
    """Bulletin from a downloaded PDF."""
    try:
        pdf = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as error:
        raise BulletinFormatError(str(path), f"unreadable PDF: {error}") from error
    return parse_bulletin_text([_page_rows(page) for page in pdf], str(path))


_ROW_TOLERANCE_PT = 3.0
_WORD_GAP_PT = 2.0


def _page_rows(page: pdfium.PdfPage) -> str:
    """
    Page text rebuilt row by row from text run positions.

    NOTE: since Oct 2026 the PDF text stream runs column-wise (all names, then all votes,
    then all proxies), so get_text_range() no longer pairs a deputy with their proxy.
    """
    textpage = page.get_textpage()
    runs = []
    for index in range(textpage.count_rects()):
        left, bottom, right, top = textpage.get_rect(index)
        text = textpage.get_text_bounded(left, bottom, right, top)
        runs.append(((bottom + top) / 2, left, right, text))
    runs.sort(key=lambda run: (-run[0], run[1]))
    rows: list[tuple[float, list[tuple[float, float, str]]]] = []
    for middle, left, right, text in runs:
        if rows and abs(rows[-1][0] - middle) <= _ROW_TOLERANCE_PT:
            rows[-1][1].append((left, right, text))
        else:
            rows.append((middle, [(left, right, text)]))
    return "\n".join(_join_runs(sorted(row)) for _, row in rows)


def _join_runs(runs: list[tuple[float, float, str]]) -> str:
    """One row's runs, left to right; runs that touch are parts of one word ('Nom du d' 'éputé')."""
    text, previous_right = "", None
    for left, right, run_text in runs:
        touches = previous_right is not None and left - previous_right < _WORD_GAP_PT
        text += run_text if touches or not text else f" {run_text}"
        previous_right = right
    return " ".join(text.split())
