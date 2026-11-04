"""
Vector parity between two Ollama servers (pinned 0.20.5 container vs the native one used for runs).

Purpose: the comparison ran on native Ollama (the pinned container is CPU-only, ~15x slower);
this checks that a sample of query and chunk vectors match the pinned version / digests closely.

Usage: python parity.py <work_dir> <variant> <model> <host_a> <host_b> <n_chunks> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

from embed_compare import doc_files
from embed_compare import GOLD_PATH
from embed_compare import load_doc
from embed_compare import load_gold
from embed_compare import make_client


def main() -> None:
    work_dir, variant, model, host_a, host_b = sys.argv[1:6]
    n_chunks, out = int(sys.argv[6]), Path(sys.argv[7])
    queries = [q.text for q in load_gold(GOLD_PATH)]
    texts = [c["page_content"] for p in doc_files(Path(work_dir), variant)
             for c in load_doc(p)["chunks"]]
    picks = np.random.default_rng(52).choice(len(texts), n_chunks, replace=False)
    sample = [texts[i] for i in picks]
    result: dict = {"model": model, "n_queries": len(queries), "n_chunks": n_chunks}
    vectors = {}
    for name, host in (("a", host_a), ("b", host_b)):
        client = make_client(model, host)
        result[f"server_{name}"] = {"host": host, **client.server_info()}
        vectors[name] = (np.array([client.embed_query(q) for q in queries]),
                         np.array(client.embed_documents(sample)))
    for i, kind in enumerate(("queries", "chunks")):
        a, b = vectors["a"][i], vectors["b"][i]
        cos = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
        result[f"cosine_{kind}"] = {"min": round(float(cos.min()), 5),
                                    "mean": round(float(cos.mean()), 5)}
    out.write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
