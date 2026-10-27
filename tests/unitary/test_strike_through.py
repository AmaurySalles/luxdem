"""
Guards the strike-through hook against Docling upgrades.

The fixture holds two real dossier pages: 8589 p.14 (black strikes, underlined insertions)
and 8030 p.20 (a strike next to a yellow highlight drawn as a 12pt-wide line).
"""
import unittest
from pathlib import Path

from docling.backend.docling_parse_backend import ThreadedDoclingParsePageBackend

from app.methodo.parsing import strike_through
from app.methodo.parsing.docling_parser import _create_converter
from app.methodo.parsing.docling_parser import parse_with_docling

_FIXTURE = Path(__file__).parent / "fixtures" / "struck_through_pages.pdf"


class StrikeThroughHookTest(unittest.TestCase):

    def test_converter_installs_hook(self) -> None:
        _create_converter()
        self.assertIs(ThreadedDoclingParsePageBackend.get_segmented_page,
                      strike_through._get_segmented_page_with_strikes)

    def test_struck_words_marked_in_chunks(self) -> None:
        text = "\n".join(chunk["page_content"] for chunk in parse_with_docling(str(_FIXTURE), {}))
        # struck run marked, underlined insertion kept
        self.assertIn("~~La~~ Les dotations financières de chaque commune ~~est~~ sont", text)
        # highlighted insertion not mistaken for a strike
        self.assertIn("choc ~~analytique~~ anaphylactique", text)


if __name__ == "__main__":
    unittest.main()
