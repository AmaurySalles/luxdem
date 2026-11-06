"""
Vector parity between the laptop's Ollama and the rented GPU Ollama, before the bulk embed (#47).

The laptop embeds queries at search time and the GPU box embeds the corpus, so both must give
the same vectors. A fixed sample (`eval/embed_parity/parity_sample.json`: German, long, table,
accented and random post-fix chunks plus the gold-set queries) is embedded one text per request
on each server, then compared on cosine, `prompt_eval_count`, Ollama version and model digest.

`time_embedding` sizes the bulk job on a fixed 1k-chunk sample, with the production batching.
"""
import gzip
import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

from app.methodo.ollama_embeddings import OllamaEmbedEmbeddings

EVAL_DIR = Path(__file__).parents[2] / "eval" / "embed_parity"
PARITY_SAMPLE = EVAL_DIR / "parity_sample.json"
TIMING_SAMPLE = EVAL_DIR / "timing_sample.json.gz"
MIN_COSINE = 0.999
WORST_SHOWN = 10

# Versions scored in the model comparison (#52): the box must serve exactly these.
PINNED_OLLAMA_VERSION = "0.40.13"
PINNED_MODEL_DIGESTS: dict[str, str] = {
    "snowflake-arctic-embed2":
        "30685f516da4acfcce0b8afee7444afc9b60bc9628f269add5f7730c5e4be3b0",
    "bge-m3": "7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab",
}


class TextKind(Enum):
    GERMAN = "german"
    LONG = "long"
    TABLE = "table"
    ACCENTED = "accented"
    RANDOM = "random"
    QUERY = "query"


@dataclass(frozen=True)
class ParityText:
    id: str
    kind: TextKind
    text: str


@dataclass(frozen=True)
class ServerEmbeddings:
    host: str
    ollama_version: str | None
    model_digest: str | None
    vectors: np.ndarray
    token_counts: list[int]


@dataclass(frozen=True)
class CosineMiss:
    id: str
    kind: TextKind
    cosine: float


@dataclass(frozen=True)
class TokenCountMismatch:
    id: str
    local: int
    remote: int


@dataclass(frozen=True)
class ParityReport:
    model: str
    local: ServerEmbeddings
    remote: ServerEmbeddings
    min_cosine: float
    mean_cosine: float
    worst: list[CosineMiss]
    count_mismatches: list[TokenCountMismatch]
    problems: list[str]

    @property
    def passed(self) -> bool:
        return not self.problems

    def summary(self) -> dict[str, object]:
        """JSON-ready report (no vectors)."""
        return {
            "model": self.model,
            "passed": self.passed,
            "problems": self.problems,
            "servers": {name: {"host": s.host, "ollama_version": s.ollama_version,
                               "model_digest": s.model_digest}
                        for name, s in (("local", self.local), ("remote", self.remote))},
            "min_cosine": round(self.min_cosine, 6),
            "mean_cosine": round(self.mean_cosine, 6),
            "worst": [{"id": w.id, "kind": w.kind.value, "cosine": round(w.cosine, 6)}
                      for w in self.worst],
            "count_mismatches": [vars(m) for m in self.count_mismatches],
        }


@dataclass(frozen=True)
class TimingResult:
    host: str
    n_chunks: int
    seconds: float
    prompt_tokens: int

    def summary(self) -> dict[str, object]:
        return {"host": self.host, "n_chunks": self.n_chunks, "seconds": round(self.seconds, 1),
                "prompt_tokens": self.prompt_tokens,
                "chunks_per_s": round(self.n_chunks / self.seconds, 1),
                "tokens_per_s": round(self.prompt_tokens / self.seconds)}


def load_parity_sample(path: Path = PARITY_SAMPLE) -> list[ParityText]:
    rows = json.loads(path.read_text())["texts"]
    return [ParityText(id=r["id"], kind=TextKind(r["kind"]), text=r["text"]) for r in rows]


def load_timing_sample(path: Path = TIMING_SAMPLE) -> list[str]:
    with gzip.open(path, "rt") as f:
        return json.load(f)


def _embed_one_by_one(model: str, host: str, texts: list[ParityText]) -> ServerEmbeddings:
    """One request per text, so each text's prompt_eval_count can be compared."""
    client = OllamaEmbedEmbeddings(model=model, host=host, batch_size=1)
    info = client.server_info()
    vectors: list[list[float]] = []
    counts: list[int] = []
    for t in texts:
        before = client.total_prompt_eval_count
        if t.kind is TextKind.QUERY:
            vectors.append(client.embed_query(t.text))
        else:
            vectors.append(client.embed_documents([t.text])[0])
        counts.append(client.total_prompt_eval_count - before)
    return ServerEmbeddings(host=host, ollama_version=info.get("ollama_version"),
                            model_digest=info.get("model_digest"),
                            vectors=np.array(vectors), token_counts=counts)


def _server_problems(name: str, server: ServerEmbeddings, model: str) -> list[str]:
    problems = []
    if server.ollama_version != PINNED_OLLAMA_VERSION:
        problems.append(f"{name} Ollama is {server.ollama_version}, pin {PINNED_OLLAMA_VERSION}")
    pinned_digest = PINNED_MODEL_DIGESTS.get(model.split(":")[0])
    if pinned_digest and server.model_digest != pinned_digest:
        problems.append(f"{name} {model} digest is {server.model_digest}, pin {pinned_digest}")
    return problems


def check_parity(model: str, local_host: str, remote_host: str,
                 texts: list[ParityText]) -> ParityReport:
    local = _embed_one_by_one(model, local_host, texts)
    remote = _embed_one_by_one(model, remote_host, texts)
    # vectors are L2-normalized by /api/embed (and by the over-long pooling)
    cosines = np.sum(local.vectors * remote.vectors, axis=1)
    order = np.argsort(cosines)
    worst = [CosineMiss(texts[i].id, texts[i].kind, float(cosines[i]))
             for i in order[:WORST_SHOWN]]
    mismatches = [TokenCountMismatch(t.id, a, b)
                  for t, a, b in zip(texts, local.token_counts, remote.token_counts) if a != b]
    problems = _server_problems("local", local, model) + _server_problems("remote", remote, model)
    if float(cosines.min()) < MIN_COSINE:
        problems.append(f"min cosine {cosines.min():.6f} < {MIN_COSINE}")
    if mismatches:
        problems.append(f"{len(mismatches)} texts with different prompt_eval_count")
    return ParityReport(model=model, local=local, remote=remote,
                        min_cosine=float(cosines.min()), mean_cosine=float(cosines.mean()),
                        worst=worst, count_mismatches=mismatches, problems=problems)


def time_embedding(model: str, host: str, texts: list[str]) -> TimingResult:
    """Embed `texts` with the production client settings (batches of 64) and time it."""
    client = OllamaEmbedEmbeddings(model=model, host=host)
    client.embed_documents(texts[:1])  # load the model before timing
    before = client.total_prompt_eval_count
    start = time.perf_counter()
    client.embed_documents(texts)
    return TimingResult(host=host, n_chunks=len(texts), seconds=time.perf_counter() - start,
                        prompt_tokens=client.total_prompt_eval_count - before)
