"""
Pilot B (#73): embed a pilot batch from the parse cache into a throwaway Chroma collection and
score it against the pilot pass bar (#72).

- Batch: `eval/pilot_b/batch.txt`, the model-comparison docs (#52, every gold source) plus the
  Pilot A sample (#70), as doc keys (`dossier/<number>`, `onh/<file>`).
- Retrieval: production search, `similarity_search(query, k=10, filter={"doc_type": ...})` per
  gold doc type. Hit = a top-10 chunk from the gold source containing the gold quote (`~~` marks
  and all whitespace removed from both: `eval/gold_set.json` match_rule).
- Baseline: the same scoring on the live pre-fix collection. Queries whose gold quote is in no
  baseline chunk (written from post-fix chunks) are left out of the flip count, as in #52.
- Chunk checks run on the whole parse cache, not only the batch.
"""
import json
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma

from app.constants import DATA_DIR
from app.methodo.chroma import embed_and_store_in_chroma
from app.methodo.parse_cache import load_cached_chunks
from app.methodo.parse_cache import load_failures
from app.methodo.parse_cache import PARSE_CACHE_DIR
from app.methodo.parse_manifest import ManifestRow
from app.methodo.parse_manifest import read_manifest

EVAL_DIR = Path(__file__).parents[2] / "eval"
GOLD_SET = EVAL_DIR / "gold_set.json"
PILOT_BATCH = EVAL_DIR / "pilot_b" / "batch.txt"
MANIFEST = DATA_DIR / "parse_manifest.jsonl"
PILOT_CHROMA_DIR = DATA_DIR / "embeddings_pilot_b"
PILOT_COLLECTION = "pilot_b"
K = 10  # production k_retrieval (topic_analysis_pipeline.py)
MAX_EMBED_TOKENS = 8192
# Same XLM-R vocabulary as snowflake-arctic-embed2 (Ollama does not expose its tokenizer)
TOKENIZER = "Snowflake/snowflake-arctic-embed-l-v2.0"

# Pass bar (#72)
MIN_HIT_RATE = 0.80
MIN_GERMAN_HIT_RATE = 0.70
MAX_HIT_TO_MISS = 2


class DocType(Enum):
    DOSSIER = "dossier"
    ONH = "onh"
    COALITION = "coalition"


@dataclass(frozen=True)
class GoldPassage:
    source: str  # doc key
    quote: str

    @property
    def doc_type(self) -> DocType:
        return DocType(self.source.split("/")[0])


@dataclass(frozen=True)
class GoldQuery:
    qid: str
    lang: str
    query: str
    gold: tuple[GoldPassage, ...]

    @property
    def doc_types(self) -> list[DocType]:
        return sorted({g.doc_type for g in self.gold}, key=lambda t: t.value)


@dataclass(frozen=True)
class QueryResult:
    qid: str
    lang: str
    hit_by_type: dict[DocType, bool]

    @property
    def hit(self) -> bool:
        return any(self.hit_by_type.values())


@dataclass(frozen=True)
class RetrievalReport:
    results: dict[str, QueryResult]

    def hit_rate(self, lang: str | None = None, doc_type: DocType | None = None) -> float | None:
        hits = [r.hit_by_type[doc_type] if doc_type else r.hit for r in self.results.values()
                if (lang is None or r.lang == lang)
                and (doc_type is None or doc_type in r.hit_by_type)]
        return sum(hits) / len(hits) if hits else None

    def summary(self) -> dict[str, Any]:
        return {"n": len(self.results), "hit@10": self.hit_rate(),
                "fr": self.hit_rate("fr"), "de": self.hit_rate("de"),
                **{f"doc_type:{t.value}": self.hit_rate(doc_type=t) for t in DocType},
                "missed": [q for q, r in self.results.items() if not r.hit]}


@dataclass(frozen=True)
class Flips:
    compared: list[str]
    hit_to_miss: list[str]
    miss_to_hit: list[str]


@dataclass(frozen=True)
class ChunkChecks:
    docs: int
    failed: int
    zero_chunk: list[str]
    over_max_tokens: list[tuple[str, int]]  # (label, tokens)
    max_tokens: int
    onh_with_strike_marks: list[str]
    dossiers_with_strike_marks: int
    dossiers: int


class PilotDocsNotCachedError(Exception):
    """Batch docs with no valid parse-cache entry: re-run the dry run first."""

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        super().__init__(f"{len(keys)} pilot docs not in the parse cache: {keys}")


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("~~", ""))


def doc_key(metadata: dict[str, Any]) -> str:
    """Gold-set doc key of a chunk: `dossier/<number>`, `onh/<file>` or `coalition`."""
    doc_type = DocType(metadata["doc_type"])
    if doc_type is DocType.DOSSIER:
        return f"dossier/{metadata['number']}"
    if doc_type is DocType.ONH:
        # pre-fix chunks carry absolute file:// urls, post-fix ones `onh/<file>`
        return f"onh/{Path(metadata['source_url']).name}"
    return doc_type.value


def load_gold(path: Path = GOLD_SET) -> list[GoldQuery]:
    rows = json.loads(path.read_text())["queries"]
    return [GoldQuery(qid=r["id"], lang=r["lang"], query=r["query"],
                      gold=tuple(GoldPassage(g["source"], g["quote"]) for g in r["gold"]))
            for r in rows]


def _cached_chunks(row: ManifestRow) -> list[dict[str, Any]] | None:
    return load_cached_chunks(PARSE_CACHE_DIR, row.source_url,
                              row.to_job(DATA_DIR).fingerprint())


def load_pilot_chunks(batch: Path = PILOT_BATCH) -> list[dict[str, Any]]:
    keys = set(batch.read_text().split())
    rows = [r for r in read_manifest(MANIFEST) if r.metadata["doc_type"] != DocType.COALITION.value
            and doc_key(r.metadata) in keys]
    cached = {doc_key(r.metadata): _cached_chunks(r) for r in rows}
    missing = sorted(keys - {k for k, chunks in cached.items() if chunks is not None})
    if missing:
        raise PilotDocsNotCachedError(missing)
    return [c for chunks in cached.values() for c in chunks]


def embed_pilot(vectorstore: Chroma, batch: Path = PILOT_BATCH) -> int:
    chunks = load_pilot_chunks(batch)
    embed_and_store_in_chroma(chunks, vectorstore)
    return len(chunks)


def _is_gold_hit(metadata: dict[str, Any], text: str, query: GoldQuery) -> bool:
    key = doc_key(metadata)
    return any(g.source == key and normalize(g.quote) in normalize(text) for g in query.gold)


def score(vectorstore: Chroma, queries: list[GoldQuery]) -> RetrievalReport:
    results = {}
    for q in queries:
        hit_by_type = {}
        for t in q.doc_types:
            docs = vectorstore.similarity_search(q.query, k=K, filter={"doc_type": t.value})
            hit_by_type[t] = any(_is_gold_hit(d.metadata, d.page_content, q) for d in docs)
        results[q.qid] = QueryResult(q.qid, q.lang, hit_by_type)
    return RetrievalReport(results)


def _chunk_texts(vectorstore: Chroma, passage: GoldPassage) -> list[str]:
    if passage.doc_type is DocType.DOSSIER:
        where = {"$and": [{"doc_type": "dossier"},
                          {"number": passage.source.removeprefix("dossier/")}]}
    else:
        where = {"doc_type": passage.doc_type.value}
    got = vectorstore.get(where=where, include=["documents", "metadatas"])
    return [text for text, meta in zip(got["documents"], got["metadatas"])
            if doc_key(meta) == passage.source]


def findable_queries(vectorstore: Chroma, queries: list[GoldQuery]) -> set[str]:
    """Queries whose every gold quote is in some chunk of its source in `vectorstore`."""
    texts: dict[str, list[str]] = {}
    for g in {g for q in queries for g in q.gold}:
        if g.source not in texts:
            texts[g.source] = [normalize(t) for t in _chunk_texts(vectorstore, g)]
    return {q.qid for q in queries
            if all(any(normalize(g.quote) in t for t in texts[g.source]) for g in q.gold)}


def flips(baseline: RetrievalReport, pilot: RetrievalReport, comparable: set[str]) -> Flips:
    common = sorted(comparable & baseline.results.keys() & pilot.results.keys())
    return Flips(
        compared=common,
        hit_to_miss=[q for q in common if baseline.results[q].hit and not pilot.results[q].hit],
        miss_to_hit=[q for q in common if not baseline.results[q].hit and pilot.results[q].hit],
    )


def check_parse_cache() -> ChunkChecks:
    """#72 chunk checks over every cached doc (shredding is merged at parse, not checkable here)."""
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)
    rows = read_manifest(MANIFEST)
    zero_chunk, over, onh_marked = [], [], []
    max_tokens = 0
    marked_dossiers = Counter()
    for row in rows:
        chunks = _cached_chunks(row)
        if chunks is None:
            continue
        if not chunks:
            zero_chunk.append(row.label)
        texts = [c["page_content"] for c in chunks]
        tokens = [len(ids) for ids in tokenizer(texts, add_special_tokens=False)["input_ids"]]
        max_tokens = max([max_tokens, *tokens])
        over += [(row.label, n) for n in tokens if n > MAX_EMBED_TOKENS]
        has_marks = any("~~" in t for t in texts)
        doc_type = DocType(row.metadata["doc_type"])
        if doc_type is DocType.ONH and has_marks:
            onh_marked.append(row.label)
        if doc_type is DocType.DOSSIER:
            marked_dossiers[has_marks] += 1
    return ChunkChecks(
        docs=len(rows), failed=len(load_failures(PARSE_CACHE_DIR)), zero_chunk=zero_chunk,
        over_max_tokens=over, max_tokens=max_tokens, onh_with_strike_marks=onh_marked,
        dossiers_with_strike_marks=marked_dossiers[True],
        dossiers=marked_dossiers[True] + marked_dossiers[False],
    )


def pass_bar_problems(pilot: RetrievalReport, flipped: Flips, checks: ChunkChecks) -> list[str]:
    problems = []
    if (rate := pilot.hit_rate()) < MIN_HIT_RATE:
        problems.append(f"hit@10 {rate:.3f} < {MIN_HIT_RATE}")
    if (rate := pilot.hit_rate("de")) < MIN_GERMAN_HIT_RATE:
        problems.append(f"German hit@10 {rate:.3f} < {MIN_GERMAN_HIT_RATE}")
    if len(flipped.hit_to_miss) > MAX_HIT_TO_MISS:
        problems.append(f"{len(flipped.hit_to_miss)} hit→miss flips > {MAX_HIT_TO_MISS}")
    if checks.failed:
        problems.append(f"{checks.failed} docs failed to parse (dropped pages or errors)")
    if checks.zero_chunk:
        problems.append(f"{len(checks.zero_chunk)} zero-chunk docs")
    # over_max_tokens is reported, not gated: the client splits and pools over-long chunks, so
    # nothing is truncated (#51). Pilot B accepted 15 merged giant tables (#73)
    if checks.onh_with_strike_marks:
        problems.append(f"strike marks in {len(checks.onh_with_strike_marks)} ONH docs")
    return problems
