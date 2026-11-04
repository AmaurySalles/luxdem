"""
Embedding-model comparison on the retrieval gold set (issue #52), pre-fix vs post-fix chunks.

Purpose: scores bge-m3 / snowflake-arctic-embed2 (/ nomic) on eval/gold_set.json with the
pass-bar metrics of issue #72, and gives Pilot B its pre-fix no-regression baseline.

Runs natively (no app deps): the repo's OllamaEmbedEmbeddings client is loaded by path with
`ecodev_core` / `langchain_core` stubbed, so prefixes and request settings are the production ones.

Layout of <work_dir> (chunks come from parse_one.py in this folder):
    <variant>/chunks/<doc>.json          parse output per doc
    <variant>/vectors/<model>/<doc>.npy  document vectors, row i = chunk i of the doc file
    queries/<model>.npy                  query vectors, gold-set order

Usage:
    python embed_compare.py embed --work-dir W --variant postfix --model bge-m3 --host H
    python embed_compare.py score --work-dir W --variants prefix postfix --models bge-m3 ... \
        --host H --acceptable acceptable_prefix_texts.json --out results/
"""
import argparse
import importlib.util
import json
import logging
import re
import sys
import types
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
CLIENT_PATH = REPO / "app" / "methodo" / "ollama_embeddings.py"
GOLD_PATH = REPO / "eval" / "gold_set.json"
K = 10  # production k_retrieval (topic_analysis_pipeline.py)
SAVED_DEPTH = 20  # ranks kept per (query, search) in rankings.json
INFOGRAPHIC_HEADING = "LE LOGEMENT en chiffres"  # cover infographic, never gold (#58)
SHINGLE_N = 5
ACCEPTABLE_MIN_CONTAINMENT = 0.5
PREFIX_VARIANT = "prefix"
POSTFIX_VARIANT = "postfix"

log = logging.getLogger("embed_compare")


class DocType(str, Enum):
    DOSSIER = "dossier"
    ONH = "onh"


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<source>::<chunk_index>"
    source: str
    doc_type: DocType
    text: str


@dataclass(frozen=True)
class GoldPassage:
    source: str
    quote: str


@dataclass(frozen=True)
class Query:
    qid: str
    lang: str
    text: str
    gold: tuple[GoldPassage, ...]
    acceptable_ids: tuple[str, ...]
    target: str | None  # strike|table|long for the passage-first German queries (q46+)

    @property
    def is_postfix_written(self) -> bool:
        """Written passage-first from post-fix chunks: no acceptable labels, prefix unverified."""
        return self.target is not None


def load_client_class() -> type:
    """
    Load OllamaEmbedEmbeddings from the repo without its app dependencies.

    Purpose: production prefixes / num_ctx / over-long split+pool, without Docker or langchain.
    """
    ecodev = types.ModuleType("ecodev_core")
    ecodev.logger_get = logging.getLogger
    lc = types.ModuleType("langchain_core")
    lc_emb = types.ModuleType("langchain_core.embeddings")
    lc_emb.Embeddings = object
    sys.modules.setdefault("ecodev_core", ecodev)
    sys.modules.setdefault("langchain_core", lc)
    sys.modules.setdefault("langchain_core.embeddings", lc_emb)
    spec = importlib.util.spec_from_file_location("ollama_embeddings", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OllamaEmbedEmbeddings


def make_client(model: str, host: str):  # -> OllamaEmbedEmbeddings (loaded dynamically)
    """Client with the settings used for every run (batch 32, 600 s timeout)."""
    return load_client_class()(model=model, host=host, keep_alive="30m", batch_size=32,
                               timeout=600.0)


def collapse(text: str) -> str:
    """Drop `~~` marks and collapse whitespace (gold_set.json match_rule, literally)."""
    return re.sub(r"\s+", " ", text.replace("~~", "")).strip()


def normalize(text: str) -> str:
    """
    Gold match rule used for scoring: drop `~~` marks and ALL whitespace ("ignoring whitespace",
    issue #72).

    NOTE: the current Docling stack (docling 2.142.1 / docling-parse 7.23.0) spaces punctuation
    differently from the Oct-12 parse the q01-q45 quotes were copied from ("2024 ." vs "2024."),
    so the collapse-only rule misses quotes that are present; results.json reports both counts.
    """
    return re.sub(r"\s+", "", text.replace("~~", ""))


def shingles(text: str) -> set[tuple[str, ...]]:
    """Lowercased word SHINGLE_N-grams; whole text as one shingle when shorter."""
    words = collapse(text).lower().split()
    if len(words) < SHINGLE_N:
        return {tuple(words)}
    return {tuple(words[i:i + SHINGLE_N]) for i in range(len(words) - SHINGLE_N + 1)}


def load_gold(path: Path) -> list[Query]:
    data = json.loads(path.read_text())
    return [Query(qid=q["id"], lang=q["lang"], text=q["query"],
                  gold=tuple(GoldPassage(g["source"], g["quote"]) for g in q["gold"]),
                  acceptable_ids=tuple(q.get("acceptable_prefix_chunks") or ()),
                  target=q.get("target"))
            for q in data["queries"]]


def doc_files(work_dir: Path, variant: str) -> list[Path]:
    return sorted((work_dir / variant / "chunks").glob("*.json"))


def load_doc(path: Path) -> dict:
    return json.loads(path.read_text())


def is_infographic(chunk_meta: dict) -> bool:
    return INFOGRAPHIC_HEADING in (chunk_meta.get("docling_headings") or [])


def embed_variant(work_dir: Path, variant: str, model: str, host: str) -> None:
    """
    Embed every parsed doc of a variant that has no vectors yet (resumable, one .npy per doc).

    Purpose: document side of the comparison; also records Ollama version + model digest.
    """
    client = make_client(model, host)
    out_dir = work_dir / variant / "vectors" / model
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "server.json").write_text(json.dumps(client.server_info(), indent=1))
    for path in doc_files(work_dir, variant):
        dest = out_dir / (path.stem + ".npy")
        if dest.exists():
            continue
        doc = load_doc(path)
        texts = [c["page_content"] for c in doc["chunks"]]
        vectors = np.array(client.embed_documents(texts), dtype=np.float32) if texts else \
            np.zeros((0, 0), dtype=np.float32)
        np.save(dest, vectors)
        log.info(f"{variant} {model} {doc['doc_id']}: {len(texts)} chunks")
    log.info(f"{variant} {model}: prompt tokens this run {client.total_prompt_eval_count}")


def embed_queries(work_dir: Path, model: str, host: str, queries: Sequence[Query]) -> np.ndarray:
    """Query vectors (production query prefix), cached per model and query list."""
    dest = work_dir / "queries" / f"{model}.npy"
    ids_path = dest.with_suffix(".ids.json")
    qids = [q.qid for q in queries]
    if dest.exists() and ids_path.exists() and json.loads(ids_path.read_text()) == qids:
        return np.load(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    client = make_client(model, host)
    vectors = np.array([client.embed_query(q.text) for q in queries], dtype=np.float32)
    np.save(dest, vectors)
    ids_path.write_text(json.dumps(qids))
    return vectors


@dataclass
class Index:
    chunks: list[Chunk]
    vectors: np.ndarray  # rows L2-normalized
    excluded_infographic: int


def load_chunks(work_dir: Path, variant: str) -> tuple[list[Chunk], list[tuple[Path, list[int]]]]:
    """Chunks of a variant minus cover-infographic ones, plus kept row numbers per doc file."""
    chunks: list[Chunk] = []
    kept_rows: list[tuple[Path, list[int]]] = []
    for path in doc_files(work_dir, variant):
        doc = load_doc(path)
        rows = []
        for i, c in enumerate(doc["chunks"]):
            meta = c["metadata"]
            if is_infographic(meta):
                continue
            rows.append(i)
            chunks.append(Chunk(chunk_id=f"{doc['doc_id']}::{meta['chunk_index']}",
                                source=doc["doc_id"], doc_type=DocType(meta["doc_type"]),
                                text=c["page_content"]))
        kept_rows.append((path, rows))
    return chunks, kept_rows


def load_index(work_dir: Path, variant: str, model: str) -> Index:
    """All chunks of a variant with their vectors, cover-infographic chunks excluded."""
    chunks, kept_rows = load_chunks(work_dir, variant)
    blocks = []
    total = 0
    for path, rows in kept_rows:
        vectors = np.load(work_dir / variant / "vectors" / model / (path.stem + ".npy"))
        n_chunks = len(load_doc(path)["chunks"])
        if len(vectors) != n_chunks:
            raise ValueError(f"{variant}/{model}/{path.stem}: {len(vectors)} vectors, "
                             f"{n_chunks} chunks")
        total += n_chunks
        if rows:
            blocks.append(vectors[rows])
    matrix = np.vstack(blocks)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    return Index(chunks=chunks, vectors=matrix, excluded_infographic=total - len(chunks))


@dataclass(frozen=True)
class Relevance:
    gold_ids: frozenset[str]  # chunk contains a gold quote (same source)
    acceptable_ids: frozenset[str]  # overlaps an acceptable pre-fix chunk (same source)
    unfindable_gold: tuple[GoldPassage, ...]  # quote in no chunk of the variant


def chunks_by_source(chunks: Iterable[Chunk]) -> dict[str, list[Chunk]]:
    by_source: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_source.setdefault(c.source, []).append(c)
    return by_source


def judge(by_source: dict[str, list[Chunk]], query: Query,
          acceptable_texts: dict[str, str]) -> Relevance:
    """
    Gold: chunk from gold.source containing the normalized quote.
    Acceptable: chunk from the same source whose 5-gram shingles cover >= 50% of an acceptable
    pre-fix chunk, or are >= 50% covered by it (labels were pre-fix chunk ids; this carries them
    across re-chunking).
    """
    gold_ids: set[str] = set()
    unfindable: list[GoldPassage] = []
    for g in query.gold:
        quote = normalize(g.quote)
        hits = [c.chunk_id for c in by_source.get(g.source, []) if quote in normalize(c.text)]
        gold_ids.update(hits)
        if not hits:
            unfindable.append(g)
    acceptable_ids: set[str] = set()
    for acc_id in query.acceptable_ids:
        source = acc_id.rsplit("::", 1)[0]
        ref = shingles(acceptable_texts[acc_id])
        for c in by_source.get(source, []):
            own = shingles(c.text)
            overlap = len(ref & own)
            if overlap / len(ref) >= ACCEPTABLE_MIN_CONTAINMENT or \
                    overlap / len(own) >= ACCEPTABLE_MIN_CONTAINMENT:
                acceptable_ids.add(c.chunk_id)
    return Relevance(frozenset(gold_ids), frozenset(acceptable_ids), tuple(unfindable))


def excluded_from_variant(variant: str, queries: Sequence[Query],
                          by_source: dict[str, list[Chunk]]) -> dict[str, list[dict]]:
    """
    Passage-first queries (q46+) dropped from pre-fix scoring: a gold quote with no pre-fix match.

    Purpose: those quotes were written from post-fix chunks, so a pre-fix miss may be a label
    artefact (e.g. `~~` placement), not retrieval; the coordinator's rule excludes them.
    """
    if variant != PREFIX_VARIANT:
        return {}
    excluded = {}
    for q in queries:
        if not q.is_postfix_written:
            continue
        missing = judge(by_source, q, {}).unfindable_gold
        if missing:
            excluded[q.qid] = [g.__dict__ for g in missing]
    return excluded


def first_rank(ranked_ids: Sequence[str], relevant: frozenset[str]) -> int | None:
    """1-based rank of the first relevant id, None if absent."""
    return next((i + 1 for i, cid in enumerate(ranked_ids) if cid in relevant), None)


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return round(sum(values) / len(values), 4) if values else None


def score_run(index: Index, query_vectors: np.ndarray, queries: Sequence[Query],
              acceptable_texts: dict[str, str], skip: Iterable[str]) -> dict:
    """
    Per-query results for one (variant, model): production-style search per doc_type.

    Returns:
        {qid: {...}} with, per doc type, the top SAVED_DEPTH ranking, the first gold rank and
        the first gold-or-acceptable rank; plus the same for one pooled (all docs) search.
    """
    skip = set(skip)
    sims = query_vectors @ index.vectors.T
    ids = np.array([c.chunk_id for c in index.chunks])
    by_source = chunks_by_source(index.chunks)
    masks = {t.value: np.array([c.doc_type == t for c in index.chunks]) for t in DocType}
    masks["pooled"] = np.ones(len(ids), dtype=bool)
    per_query: dict[str, dict] = {}
    for qi, q in enumerate(queries):
        if q.qid in skip:
            continue
        rel = judge(by_source, q, acceptable_texts)
        relevant = rel.gold_ids | rel.acceptable_ids
        searches: dict[str, dict] = {}
        for name, mask in masks.items():
            order = np.argsort(-sims[qi][mask], kind="stable")
            ranked = ids[mask][order]
            scores = sims[qi][mask][order]
            searches[name] = {
                "gold_rank": first_rank(ranked, rel.gold_ids),
                "relevant_rank": first_rank(ranked, relevant),
                "top": [{"id": str(cid), "score": round(float(s), 5),
                         "gold": str(cid) in rel.gold_ids,
                         "acceptable": str(cid) in rel.acceptable_ids}
                        for cid, s in zip(ranked[:SAVED_DEPTH], scores[:SAVED_DEPTH])],
            }
        per_query[q.qid] = {
            "lang": q.lang,
            "slice": query_slice(q),
            "target": q.target,
            "gold_doc_types": sorted({g.source.split("/")[0] for g in q.gold}),
            "n_gold_chunks": len(rel.gold_ids),
            "n_acceptable_chunks": len(rel.acceptable_ids),
            "unfindable_gold": [g.__dict__ for g in rel.unfindable_gold],
            "searches": searches,
        }
    return per_query


def query_slice(q: Query) -> str:
    """fr | de_old (q41-q45, pooled labels) | de_new (q46+, passage-first, gold only)."""
    if q.lang != "de":
        return q.lang
    return "de_new" if q.is_postfix_written else "de_old"


def is_hit(result: dict, search: str) -> bool:
    rank = result["searches"][search]["gold_rank"]
    return rank is not None and rank <= K


def query_hit(result: dict) -> bool:
    """Query hit@10: a gold chunk in the top 10 of the search for any of its gold doc types."""
    return any(is_hit(result, t) for t in result["gold_doc_types"])


def query_rr(result: dict, rank_key: str) -> float:
    """Reciprocal rank, best over the query's gold doc-type searches (no cutoff)."""
    ranks = [result["searches"][t][rank_key] for t in result["gold_doc_types"]]
    return max((1 / r for r in ranks if r is not None), default=0.0)


def summarize(per_query: dict) -> dict:
    """Aggregate metrics for one (variant, model)."""
    def block(qids: list[str]) -> dict:
        return {
            "n": len(qids),
            "hit@10": mean(float(query_hit(per_query[q])) for q in qids),
            "mrr_gold+acceptable": mean(query_rr(per_query[q], "relevant_rank") for q in qids),
            "mrr_gold": mean(query_rr(per_query[q], "gold_rank") for q in qids),
        }

    qids = list(per_query)
    out = {"overall": block(qids), "fr": block([q for q in qids if per_query[q]["lang"] == "fr"]),
           "de_all": block([q for q in qids if per_query[q]["lang"] == "de"])}
    for name in ("de_old", "de_new"):
        out[name] = block([q for q in qids if per_query[q]["slice"] == name])
    for t in DocType:
        typed = [q for q in qids if t.value in per_query[q]["gold_doc_types"]]
        out[f"doc_type:{t.value}"] = {
            "n": len(typed),
            "hit@10": mean(float(is_hit(per_query[q], t.value)) for q in typed),
            "mrr_gold+acceptable": mean(
                1 / r if (r := per_query[q]["searches"][t.value]["relevant_rank"]) else 0.0
                for q in typed),
        }
    out["pooled_search"] = {
        "hit@10": mean(float(is_hit(per_query[q], "pooled")) for q in qids),
        "mrr_gold+acceptable": mean(
            1 / r if (r := per_query[q]["searches"]["pooled"]["relevant_rank"]) else 0.0
            for q in qids),
    }
    out["unfindable_gold_passages"] = sum(len(per_query[q]["unfindable_gold"]) for q in qids)
    out["missed_queries"] = [q for q in qids if not query_hit(per_query[q])]
    return out


def flips(pre: dict, post: dict) -> dict[str, list[str]]:
    """Query-level hit@10 changes pre-fix -> post-fix for one model (queries scored in both)."""
    common = [q for q in post if q in pre]
    return {
        "n_compared": len(common),
        "hit_to_miss": [q for q in common if query_hit(pre[q]) and not query_hit(post[q])],
        "miss_to_hit": [q for q in common if not query_hit(pre[q]) and query_hit(post[q])],
        "miss_both": [q for q in common if not query_hit(pre[q]) and not query_hit(post[q])],
    }


def unfindable_quotes(by_source: dict[str, list[Chunk]], queries: Sequence[Query],
                      rule: Callable[[str], str]) -> list[dict]:
    """Gold passages whose quote is in no (non-infographic) chunk of its source under `rule`."""
    return [{"qid": q.qid, "source": g.source, "quote": g.quote}
            for q in queries for g in q.gold
            if not any(rule(g.quote) in rule(c.text) for c in by_source.get(g.source, []))]


def chunk_stats(work_dir: Path, variant: str, queries: Sequence[Query]) -> dict:
    docs = [load_doc(p) for p in doc_files(work_dir, variant)]
    chunks = [c for d in docs for c in d["chunks"]]
    by_source = chunks_by_source(load_chunks(work_dir, variant)[0])
    return {
        "docs": len(docs),
        "chunks": len(chunks),
        "infographic_chunks": sum(is_infographic(c["metadata"]) for c in chunks),
        "zero_chunk_docs": [d["doc_id"] for d in docs if not d["chunks"]],
        "docs_with_strike_marks": sorted(d["doc_id"] for d in docs
                                         if any("~~" in c["page_content"] for c in d["chunks"])),
        "conversion": {d["doc_id"]: d.get("conversion", "docling_convert") for d in docs},
        "gold_quotes_unfindable_collapse_rule": unfindable_quotes(by_source, queries, collapse),
        "gold_quotes_unfindable_no_whitespace_rule": unfindable_quotes(by_source, queries,
                                                                       normalize),
    }


def run_score(args: argparse.Namespace) -> None:
    """
    Score every (variant, model), write results.json, rankings.json and scores_table.md.

    Purpose: the numbers posted on #52; rankings.json keeps per-query rankings and the top-10
    passage texts so labels can be re-pooled without re-embedding.
    """
    work_dir = Path(args.work_dir)
    queries = load_gold(GOLD_PATH)
    acceptable_texts = json.loads(Path(args.acceptable).read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {"k": K, "gold_set": str(GOLD_PATH.relative_to(REPO)),
                     "n_queries": len(queries), "variants": {}, "excluded_queries": {},
                     "models": {}, "runs": {}, "flips": {}}
    rankings: dict = {"k": K, "depth": SAVED_DEPTH, "runs": {}, "passages": {}}
    for variant in args.variants:
        results["variants"][variant] = chunk_stats(work_dir, variant, queries)
        by_source = chunks_by_source(load_chunks(work_dir, variant)[0])
        results["excluded_queries"][variant] = excluded_from_variant(variant, queries, by_source)
    for model in args.models:
        query_vectors = embed_queries(work_dir, model, args.host, queries)
        per_variant: dict[str, dict] = {}
        for variant in args.variants:
            index = load_index(work_dir, variant, model)
            server = json.loads((work_dir / variant / "vectors" / model / "server.json")
                                .read_text())
            results["models"].setdefault(model, {})[variant] = server
            per_query = score_run(index, query_vectors, queries, acceptable_texts,
                                  skip=results["excluded_queries"][variant])
            per_variant[variant] = per_query
            run = f"{variant}/{model}"
            results["runs"][run] = {"indexed_chunks": len(index.chunks),
                                    "excluded_infographic": index.excluded_infographic,
                                    **summarize(per_query)}
            rankings["runs"][run] = per_query
            texts = {c.chunk_id: c.text for c in index.chunks}
            for res in per_query.values():
                for search in res["searches"].values():
                    for hit in search["top"][:K]:
                        rankings["passages"].setdefault(variant, {})[hit["id"]] = texts[hit["id"]]
        if {PREFIX_VARIANT, POSTFIX_VARIANT} <= per_variant.keys():
            results["flips"][model] = flips(per_variant[PREFIX_VARIANT],
                                            per_variant[POSTFIX_VARIANT])
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    (out_dir / "rankings.json").write_text(json.dumps(rankings, ensure_ascii=False))
    (out_dir / "scores_table.md").write_text(render_markdown(results))
    print(render_markdown(results))


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def render_markdown(results: dict) -> str:
    """
    Scores tables + flips from results.json.

    Purpose: the human-readable summary committed next to results.json and linked from #52.
    """
    lines = ["| Run | n | hit@10 | MRR (gold+acc) | FR hit@10 | DE all hit@10 | DE q41-45 "
             "| DE q46-56 | dossier hit@10 | ONH hit@10 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for run, s in results["runs"].items():
        lines.append(
            f"| {run} | {s['overall']['n']} | {fmt(s['overall']['hit@10'])} "
            f"| {fmt(s['overall']['mrr_gold+acceptable'])} | {fmt(s['fr']['hit@10'])} "
            f"| {fmt(s['de_all']['hit@10'])} ({s['de_all']['n']}) "
            f"| {fmt(s['de_old']['hit@10'])} ({s['de_old']['n']}) "
            f"| {fmt(s['de_new']['hit@10'])} ({s['de_new']['n']}) "
            f"| {fmt(s['doc_type:dossier']['hit@10'])} | {fmt(s['doc_type:onh']['hit@10'])} |")
    lines += ["", "| Run | MRR FR | MRR DE all | MRR DE q41-45 | MRR DE q46-56 (gold only) "
              "| pooled hit@10 | pooled MRR |", "|---|---|---|---|---|---|---|"]
    for run, s in results["runs"].items():
        lines.append(
            f"| {run} | {fmt(s['fr']['mrr_gold+acceptable'])} "
            f"| {fmt(s['de_all']['mrr_gold+acceptable'])} "
            f"| {fmt(s['de_old']['mrr_gold+acceptable'])} "
            f"| {fmt(s['de_new']['mrr_gold+acceptable'])} "
            f"| {fmt(s['pooled_search']['hit@10'])} "
            f"| {fmt(s['pooled_search']['mrr_gold+acceptable'])} |")
    lines += ["", "| Model | compared | hit→miss | miss→hit | miss both |", "|---|---|---|---|---|"]
    for model, f in results["flips"].items():
        lines.append(f"| {model} | {f['n_compared']} | {', '.join(f['hit_to_miss']) or '-'} "
                     f"| {', '.join(f['miss_to_hit']) or '-'} "
                     f"| {', '.join(f['miss_both']) or '-'} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = parser.add_subparsers(dest="command", required=True)
    embed = sub.add_parser("embed")
    embed.add_argument("--work-dir", required=True)
    embed.add_argument("--variant", required=True)
    embed.add_argument("--model", required=True)
    embed.add_argument("--host", required=True)
    score = sub.add_parser("score")
    score.add_argument("--work-dir", required=True)
    score.add_argument("--variants", nargs="+", required=True)
    score.add_argument("--models", nargs="+", required=True)
    score.add_argument("--host", required=True)
    score.add_argument("--acceptable", required=True)
    score.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "embed":
        embed_variant(Path(args.work_dir), args.variant, args.model, args.host)
    else:
        run_score(args)


if __name__ == "__main__":
    main()
