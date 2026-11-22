"""Summary input stays under the chat context window (#98: 8751 lost its system prompt)."""
import unittest

from app.methodo.summarizer import join_chunks


class JoinChunksTest(unittest.TestCase):

    def test_keeps_all_chunks_under_budget(self) -> None:
        self.assertEqual(join_chunks(["a", "b"], max_chars=100), "a\n\n---\n\nb")

    def test_stops_before_chunk_that_overflows(self) -> None:
        self.assertEqual(join_chunks(["a" * 40, "b" * 40, "c"], max_chars=60), "a" * 40)

    def test_cuts_single_oversized_first_chunk(self) -> None:
        self.assertEqual(join_chunks(["a" * 100], max_chars=60), "a" * 60)


if __name__ == "__main__":
    unittest.main()
