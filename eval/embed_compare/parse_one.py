"""Parse one sample doc with the mounted code (pre- or post-fix) and dump chunks + Docling headings.

Runs inside luxdem:latest: python /work/parse_one.py <variant> <doc_id> <pdf_path>
Writes /work/<variant>/chunks/<doc_id with / -> __>.json.
Exits 1 on failure (logged to failed.jsonl).

Post-fix runs also save the converted DoclingDocument. The pre-fix run reuses it when it holds no
`~~` mark (the strike-through hook changed nothing, so conversion is identical) and only re-runs
the pre-fix chunking code on it; docs with marks are converted again with the pre-fix code.
"""
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from app.methodo.parsing import docling_parser as dp

variant, doc_id, pdf_path = sys.argv[1], sys.argv[2], sys.argv[3]
root = Path("/work") / variant
stem = doc_id.replace("/", "__")
out = root / "chunks" / (stem + ".json")
out.parent.mkdir(parents=True, exist_ok=True)
postfix_doc = Path("/work/postfix/docs") / (stem + ".json")

_captured: dict = {}
_orig_merge = dp._merge_table_shredded_chunks
_orig_get_converter = dp._get_converter


def _capturing_merge(chunks: list) -> list:
    merged = _orig_merge(chunks)
    _captured["merged"] = merged
    return merged


class _CapturingConverter:
    def __init__(self, inner) -> None:
        self._inner = inner

    def convert(self, source: str):
        result = self._inner.convert(source)
        _captured["document"] = result.document
        return result


class _StoredConverter:
    def __init__(self, document) -> None:
        self._document = document

    def convert(self, source: str):
        return SimpleNamespace(document=self._document)


dp._merge_table_shredded_chunks = _capturing_merge
conversion = "docling_convert"
if variant == "prefix" and postfix_doc.exists() and "~~" not in postfix_doc.read_text():
    from docling_core.types.doc import DoclingDocument
    stored = DoclingDocument.load_from_json(postfix_doc)
    dp._get_converter = lambda: _StoredConverter(stored)
    conversion = "reused_postfix_document_no_strike_marks"
else:
    dp._get_converter = lambda: _CapturingConverter(_orig_get_converter())

doc_type = doc_id.split("/")[0]
metadata = {"source_url": doc_id, "doc_type": doc_type}
t0 = time.time()
try:
    if doc_type == "onh":
        try:
            from app.methodo.onh_pipeline import parse_onh_publication  # post-fix only (PR #74)
            chunks = parse_onh_publication(pdf_path, metadata)
            parse_call = "parse_onh_publication"
        except ImportError:
            chunks = dp.parse_with_docling(pdf_path, metadata, min_chunk_words=50)
            parse_call = "parse_with_docling(min_chunk_words=50)"
    else:
        chunks = dp.parse_with_docling(pdf_path, metadata)
        parse_call = "parse_with_docling"
except Exception as e:  # recorded per doc; the driver lists failures
    err = {"doc_id": doc_id, "variant": variant, "error": f"{type(e).__name__}: {e}",
           "dropped_pages": getattr(e, "dropped_pages", None),
           "seconds": round(time.time() - t0, 1)}
    with open(root / "failed.jsonl", "a") as f:
        f.write(json.dumps(err, ensure_ascii=False) + "\n")
    print("FAILED", err, flush=True)
    sys.exit(1)

if variant == "postfix" and "document" in _captured:
    postfix_doc.parent.mkdir(parents=True, exist_ok=True)
    _captured["document"].save_as_json(postfix_doc)

# attach Docling heading path (chunk.meta.headings) to each output chunk by in-order text match
merged = _captured.get("merged", [])
j = 0
for c in chunks:
    while j < len(merged) and merged[j].text != c["page_content"]:
        j += 1
    headings = list(merged[j].meta.headings or []) if j < len(merged) else None
    c["metadata"]["docling_headings"] = headings
    j += 1

json.dump({"doc_id": doc_id, "variant": variant, "parse_call": parse_call, "conversion": conversion,
           "seconds": round(time.time() - t0, 1), "chunks": chunks},
          open(out, "w"), ensure_ascii=False)
print(f"{variant} {doc_id}: {len(chunks)} chunks in {time.time() - t0:.0f}s ({conversion})",
      flush=True)
