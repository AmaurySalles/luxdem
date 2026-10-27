"""
Mark struck-through words in Docling's PDF text cells as `~~…~~`.

Dossier "textes coordonnés" show a bill's deletions as struck-through text next to the
new wording (`31 décembre ~~2032~~ 2036`). Docling extracts struck words as live text, so
without marking, chunks read as if both versions were in force.

The hook patches `ThreadedDoclingParsePageBackend.get_segmented_page`, which feeds both
the text cells (page preprocessing) and the word cells (table structure). Strike lines
come from the page's vector shapes; a word is struck when a thin horizontal line crosses
the middle of its box over most of its width. Underlines sit at the word's baseline and
are kept.

NOTE: Struck cells are rewritten, never removed: removing them lets Docling's OCR text
fill the gap with garbage. A hook exception makes Docling skip the page, which
`parse_with_docling` turns into `DoclingPagesDroppedError`.
NOTE: Relies on private Docling internals (`_result._require_page_decoder`), so Docling
is pinned to exact versions and `tests/unitary/test_strike_through.py` fails if the hook
stops firing.
"""
from bisect import bisect_left
from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby
from itertools import pairwise
from threading import Lock

from docling.backend.docling_parse_backend import ThreadedDoclingParsePageBackend
from docling_core.types.doc.page import SegmentedPdfPage
from docling_core.types.doc.page import TextCell

STRIKE_MARK = "~~"

# A strike line is a horizontal path at most this thick, counting both its geometric height
# and its stroke width: highlights are drawn as zero-height lines with a ~12pt stroke.
_MAX_STRIKE_THICKNESS_PT = 1.5
# Where a strike line crosses a word, as a fraction of the word box height from its top.
# Strikes sit at ~0.6, underlines at ~1.1.
_STRIKE_BAND = (0.4, 0.8)
_MIN_WORD_COVERAGE = 0.6
_MIN_LINE_TEXT_COVERAGE = 0.7

_original_get_segmented_page = ThreadedDoclingParsePageBackend.get_segmented_page
_mark_lock = Lock()


@dataclass(frozen=True)
class StrikeLine:
    """A thin horizontal line on the page, in top-left-origin coordinates."""
    y: float
    left: float
    right: float


def install_strike_through_hook() -> None:
    """
    Patch Docling's page backend so every parsed page comes out with struck words marked.

    Purpose: Called from `_create_converter()` in `docling_parser.py`. Idempotent.
    """
    ThreadedDoclingParsePageBackend.get_segmented_page = _get_segmented_page_with_strikes


def _get_segmented_page_with_strikes(self: ThreadedDoclingParsePageBackend,
                                     ) -> SegmentedPdfPage | None:
    """Wraps the original, marking the cached page once (it is fetched by several stages)."""
    seg_page = _original_get_segmented_page(self)
    if seg_page is None:
        return None
    with _mark_lock:
        if not getattr(self, "_strikes_marked", False):
            mark_struck_words(seg_page, read_strike_lines(self))
            self._strikes_marked = True
    return seg_page


def read_strike_lines(backend: ThreadedDoclingParsePageBackend) -> list[StrikeLine]:
    """
    Thin horizontal subpaths of the page's vector shapes, colour-agnostic.

    Purpose: Strike-line source for `mark_struck_words`. Red and black strikes both count.
    """
    page_height = backend.get_size().height
    lines = []
    for shape in backend._result._require_page_decoder().get_page_shapes():
        if shape.get_line_width() > _MAX_STRIKE_THICKNESS_PT:
            continue
        xs, ys = list(shape.get_x()), list(shape.get_y())
        for start, end in pairwise(shape.get_i()):
            sub_x, sub_y = xs[start:end], ys[start:end]
            if not sub_x:
                continue
            width, height = max(sub_x) - min(sub_x), max(sub_y) - min(sub_y)
            if height <= _MAX_STRIKE_THICKNESS_PT and width > height:
                y_mid = page_height - (max(sub_y) + min(sub_y)) / 2
                lines.append(StrikeLine(y=y_mid, left=min(sub_x), right=max(sub_x)))
    return lines


def mark_struck_words(seg_page: SegmentedPdfPage, strike_lines: Sequence[StrikeLine]) -> None:
    """
    Wrap struck runs in `~~…~~`, in both text-line cells and word cells.

    Purpose: Text lines feed Docling's text items, word cells its table cells. A line's text
    is rewritten around its struck words so its original spacing is kept.
    """
    struck_ids = _struck_word_ids(seg_page.word_cells, strike_lines)
    if not struck_ids:
        return

    words_by_y = sorted(seg_page.word_cells, key=_center_y)
    word_ys = [_center_y(word) for word in words_by_y]
    for textline in seg_page.textline_cells:
        box = textline.rect.to_bounding_box()
        in_band = words_by_y[bisect_left(word_ys, box.t):bisect_right(word_ys, box.b)]
        words = sorted((w for w in in_band if box.l <= _center_x(w) <= box.r), key=_center_x)
        if any(id(word) in struck_ids for word in words):
            textline.text = _mark_runs(textline.text, words, struck_ids)

    for word in seg_page.word_cells:
        if id(word) in struck_ids:
            word.text = f"{STRIKE_MARK}{word.text}{STRIKE_MARK}"


def _struck_word_ids(words: Sequence[TextCell], strike_lines: Sequence[StrikeLine]) -> set[int]:
    """
    Ids of the words crossed by a strike line over most of their width.

    NOTE: A line only counts if the words in its strike band cover most of its length: chart
    gridlines cross a few small labels, strikes run across text.
    """
    lines_by_y = sorted(strike_lines, key=lambda line: line.y)
    line_ys = [line.y for line in lines_by_y]
    crossings = {id(word): _crossings(word, lines_by_y, line_ys) for word in words}
    text_cover: Counter[StrikeLine] = Counter()
    for word_crossings in crossings.values():
        for line, left, right in word_crossings:
            text_cover[line] += right - left
    through_text = {
        line for line, cover in text_cover.items()
        if cover >= _MIN_LINE_TEXT_COVERAGE * (line.right - line.left)
    }
    return {
        id(word) for word in words
        if _covered_width([(left, right) for line, left, right in crossings[id(word)]
                           if line in through_text]) >= _MIN_WORD_COVERAGE * _width(word)
    }


def _crossings(word: TextCell, lines_by_y: list[StrikeLine],
               line_ys: list[float]) -> list[tuple[StrikeLine, float, float]]:
    """Strike lines inside the word's strike band, with the x-span they share with it."""
    box = word.rect.to_bounding_box()
    height = box.b - box.t
    if box.r <= box.l or height <= 0:
        return []
    band_top, band_bottom = (box.t + fraction * height for fraction in _STRIKE_BAND)
    return [
        (line, max(line.left, box.l), min(line.right, box.r))
        for line in lines_by_y[bisect_left(line_ys, band_top):bisect_right(line_ys, band_bottom)]
        if line.left < box.r and line.right > box.l
    ]


def _covered_width(spans: list[tuple[float, float]]) -> float:
    """Length of the union of x-spans."""
    covered, reach = 0.0, float("-inf")
    for left, right in sorted(spans):
        covered += max(0.0, right - max(left, reach))
        reach = max(reach, right)
    return covered


def _mark_runs(text: str, words: list[TextCell], struck_ids: set[int]) -> str:
    """
    Wrap each run of consecutive struck words of `text` in `~~…~~`.

    NOTE: Falls back to rebuilding the line from its words, space-joined, when a word's text
    can't be found in the line's text in order.
    """
    spans = []
    cursor = 0
    for word in words:
        start = text.find(word.text, cursor)
        if start < 0:
            return _join_marked(words, struck_ids)
        cursor = start + len(word.text)
        spans.append((start, cursor, id(word) in struck_ids))

    parts = []
    position = 0
    for struck, run in groupby(spans, key=lambda span: span[2]):
        if not struck:
            continue
        run = list(run)
        start, end = run[0][0], run[-1][1]
        parts += [text[position:start], STRIKE_MARK, text[start:end], STRIKE_MARK]
        position = end
    parts.append(text[position:])
    return "".join(parts)


def _join_marked(words: list[TextCell], struck_ids: set[int]) -> str:
    """Space-joined words with each struck run wrapped in `~~…~~`."""
    runs = []
    for struck, run in groupby(words, key=lambda word: id(word) in struck_ids):
        run_text = " ".join(word.text for word in run)
        runs.append(f"{STRIKE_MARK}{run_text}{STRIKE_MARK}" if struck else run_text)
    return " ".join(runs)


def _width(cell: TextCell) -> float:
    box = cell.rect.to_bounding_box()
    return box.r - box.l


def _center_x(cell: TextCell) -> float:
    box = cell.rect.to_bounding_box()
    return (box.l + box.r) / 2


def _center_y(cell: TextCell) -> float:
    box = cell.rect.to_bounding_box()
    return (box.t + box.b) / 2
