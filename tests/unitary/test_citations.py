"""Citation checks on verdict text (#101, #103)."""
import unittest

from app.methodo.evidence import find_citations, find_overcited_sentences


class CitationTest(unittest.TestCase):

    def test_finds_grouped_ids(self) -> None:
        self.assertEqual(find_citations("Loi votée [dossier/8589#42; onh/note-38.pdf#3]."),
                         ["dossier/8589#42", "onh/note-38.pdf#3"])

    def test_flags_only_sentences_over_three_ids(self) -> None:
        dumped = ("Les aides ont augmenté [dossier/1#1; dossier/1#2; dossier/2#3; "
                  "onh/note-38.pdf#4].")
        text = f"Le loyer est plafonné [dossier/8589#42]. {dumped} Rien d'autre."
        self.assertEqual(find_overcited_sentences(text), [dumped])

    def test_file_extension_dot_does_not_split_sentence(self) -> None:
        text = "Constat [onh/note-38.pdf#1; onh/note-38.pdf#2; onh/a.pdf#3; onh/b.pdf#4]."
        self.assertEqual(find_overcited_sentences(text), [text])


if __name__ == "__main__":
    unittest.main()
