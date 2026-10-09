"""
LangChain Embeddings client over Ollama's /api/embed (decision: issue #48, implementation: #51).

Every request setting is explicit: sub-batching, truncate=False, num_ctx/num_batch, keep_alive,
timeout, retries and per-model prefixes.
Over-long inputs are never cut: see OllamaEmbedEmbeddings._embed_overlong.
"""
import time
from dataclasses import dataclass
from typing import Any
from typing import Sequence

import httpx
import numpy as np
import ollama
import requests
from ecodev_core import logger_get
from langchain_core.embeddings import Embeddings

log = logger_get(__name__)

DEFAULT_BATCH_SIZE = 64
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_S = 1.0
_CONTEXT_ERROR = "context length"


@dataclass(frozen=True)
class EmbedModelProfile:
    """Per-model request settings. num_ctx is also used as num_batch."""
    num_ctx: int | None
    document_prefix: str = ""
    query_prefix: str = ""


# Keyed by model name without tag. num_batch must match num_ctx or bert-family models stay
# capped at 2048 tokens; nomic is clamped to its 2048 trained context by Ollama anyway.
MODEL_PROFILES: dict[str, EmbedModelProfile] = {
    "bge-m3": EmbedModelProfile(num_ctx=8192),
    "snowflake-arctic-embed2": EmbedModelProfile(num_ctx=8192, query_prefix="query: "),
    "nomic-embed-text": EmbedModelProfile(
        num_ctx=2048,
        document_prefix="search_document: ",
        query_prefix="search_query: ",
    ),
}


def _base_model_name(model: str) -> str:
    return model.split(":")[0]


def _is_context_error(error: ollama.ResponseError) -> bool:
    return error.status_code == 400 and _CONTEXT_ERROR in str(error.error).lower()


def _split_in_two(text: str) -> tuple[str, str]:
    """Split text near its middle, preferring a paragraph, line or word boundary."""
    mid = len(text) // 2
    for sep in ("\n\n", "\n", " "):
        left = text.rfind(sep, 0, mid)
        right = text.find(sep, mid)
        candidates = [i for i in (left, right) if i > 0]
        if candidates:
            cut = min(candidates, key=lambda i: abs(i - mid))
            return text[:cut], text[cut:]
    return text[:mid], text[mid:]


class OllamaEmbedEmbeddings(Embeddings):
    """Embeddings over ollama.Client.embed (/api/embed, L2-normalized vectors)."""

    def __init__(
        self,
        model: str,
        host: str,
        keep_alive: str | float | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_s: float = DEFAULT_BACKOFF_S,
        profile: EmbedModelProfile | None = None,
    ) -> None:
        self.model = model
        self.host = host
        self.keep_alive = keep_alive
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        if profile is None:
            profile = MODEL_PROFILES.get(_base_model_name(model))
            if profile is None:
                log.warning(f"No embedding profile for {model}: no prefixes, Ollama defaults")
                profile = EmbedModelProfile(num_ctx=None)
        self.profile = profile
        self.options: dict[str, Any] = (
            {"num_ctx": profile.num_ctx, "num_batch": profile.num_ctx} if profile.num_ctx else {}
        )
        self.total_prompt_eval_count = 0
        self._client = ollama.Client(host=host, timeout=timeout)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [self.profile.document_prefix + t for t in texts]
        start_count = self.total_prompt_eval_count
        vectors: list[list[float]] = []
        for i in range(0, len(prefixed), self.batch_size):
            vectors.extend(self._embed_batch(prefixed[i:i + self.batch_size]))
        log.info(
            f"Embedded {len(texts)} docs with {self.model}: "
            f"{self.total_prompt_eval_count - start_count} prompt tokens "
            f"(session total {self.total_prompt_eval_count})"
        )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([self.profile.query_prefix + text])[0]

    def server_info(self) -> dict[str, str]:
        """Ollama version and model digest, for collection metadata. Missing keys on failure."""
        info: dict[str, str] = {}
        try:
            response = requests.get(f"{self.host}/api/version", timeout=5)
            response.raise_for_status()
            info["ollama_version"] = str(response.json()["version"])
        except (requests.RequestException, KeyError, ValueError) as e:
            log.warning(f"Could not read Ollama version: {e}")
        try:
            wanted = self.model if ":" in self.model else f"{self.model}:latest"
            for m in self._client.list().models:
                if m.model == wanted and m.digest:
                    info["model_digest"] = m.digest
        except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as e:
            log.warning(f"Could not read digest of {self.model}: {e}")
        return info

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            return self._embed_request(texts)[0]
        except ollama.ResponseError as e:
            if not _is_context_error(e):
                raise
        # At least one text exceeds the context: redo them one by one to isolate it.
        return [self._embed_one(t)[0] for t in texts]

    def _embed_one(self, text: str) -> tuple[list[float], int]:
        """Embed one text, splitting it if it is over the model context."""
        try:
            vectors, count = self._embed_request([text])
            return vectors[0], count
        except ollama.ResponseError as e:
            if not _is_context_error(e):
                raise
        return self._embed_overlong(text)

    def _embed_overlong(self, text: str) -> tuple[list[float], int]:
        """
        Text over the model context: split it in two (on a paragraph/line/word boundary), embed
        each half (recursively), and return the token-weighted mean of the halves, re-normalized.
        Keeps one vector per chunk (Chroma IDs unchanged) and no content is dropped.
        The halves keep the document prefix so each part is embedded as a document.
        """
        prefix = self.profile.document_prefix
        body = text[len(prefix):] if prefix and text.startswith(prefix) else text
        if len(body) < 2:
            raise ValueError(f"Cannot split over-long input further: {text!r}")
        log.warning(
            f"Input over {self.model} context ({len(body)} chars), split and mean-pooled: "
            f"{body[:120]!r}..."
        )
        embedded = [self._embed_one(prefix + half) for half in _split_in_two(body)]
        weights = np.array([max(count, 1) for _, count in embedded], dtype=float)
        mean = np.average(np.array([v for v, _ in embedded]), axis=0, weights=weights)
        return (mean / np.linalg.norm(mean)).tolist(), int(weights.sum())

    def _embed_request(self, texts: Sequence[str]) -> tuple[list[list[float]], int]:
        """One /api/embed call with retry and backoff on connection errors and 5xx."""
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.embed(
                    model=self.model,
                    input=list(texts),
                    truncate=False,
                    options=self.options or None,
                    keep_alive=self.keep_alive,
                )
                count = response.prompt_eval_count or 0
                self.total_prompt_eval_count += count
                return [list(v) for v in response.embeddings], count
            except ollama.ResponseError as e:
                if e.status_code < 500 or attempt == self.max_retries:
                    raise
                error: Exception = e
            except (ConnectionError, httpx.TransportError) as e:
                if attempt == self.max_retries:
                    raise
                error = e
            delay = self.backoff_s * 2 ** attempt
            log.warning(f"Ollama embed failed ({error!r}), retry {attempt + 1} in {delay:.1f}s")
            time.sleep(delay)
        raise AssertionError("unreachable")
