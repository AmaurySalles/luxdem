"""The chat client refuses a host that lacks the pinned model digest (#98, #103)."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.methodo import local_llm
from app.methodo.local_llm import ChatModelMismatchError, get_local_llm_client


def _fake_client(models: list[tuple[str, str]]) -> SimpleNamespace:
    listing = SimpleNamespace(models=[SimpleNamespace(model=m, digest=d) for m, d in models])
    return SimpleNamespace(list=lambda: listing)


class ChatModelPinTest(unittest.TestCase):

    def _client_for(self, models: list[tuple[str, str]]) -> SimpleNamespace:
        with patch.object(local_llm, "Client", return_value=_fake_client(models)):
            return get_local_llm_client("http://gpu:11434")

    def test_accepts_pinned_digest(self) -> None:
        full_digest = local_llm.CHAT_MODEL_DIGEST + "0" * 52
        self.assertIsNotNone(self._client_for([(local_llm.LOCAL_LLM_MODEL, full_digest)]))

    def test_rejects_moved_tag(self) -> None:
        with self.assertRaises(ChatModelMismatchError) as caught:
            self._client_for([(local_llm.LOCAL_LLM_MODEL, "56671c2ab938")])
        self.assertEqual(caught.exception.found_digest, "56671c2ab938")

    def test_rejects_host_without_model(self) -> None:
        with self.assertRaises(ChatModelMismatchError) as caught:
            self._client_for([("snowflake-arctic-embed2:latest", "30685f516da4")])
        self.assertIsNone(caught.exception.found_digest)


if __name__ == "__main__":
    unittest.main()
