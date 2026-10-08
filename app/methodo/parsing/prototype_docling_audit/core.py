"""
PROTOTYPE — throwaway. Answers: does Docling's chunking of LuxDem PDFs preserve
correct page position, reading order, and parent-child structure?
See .scratch/docling-parsing-audit/issues/01-parse-vs-source-comparison.md

Pure extraction + flagging logic, no I/O beyond the Docling conversion itself
(which *is* the thing being inspected). No terminal code here — the TUI in
tui.py is a thin shell over this module.
"""
from dataclasses import dataclass, field

# Matches the existing ONH fix's threshold (app/methodo/onh_pipeline.py
# ONH_MIN_CHUNK_WORDS) so "short_fragment" flags line up with what that fix
# already silently drops for ONH docs (and would also catch elsewhere).
SHORT_FRAGMENT_WORDS = 50


@dataclass
class ChunkRecord:
    index: int
    text: str
    word_count: int
    pages: list[int]
    labels: list[str]
    headings: list[str]
    doc_item_refs: list[str]
    flags: list[str] = field(default_factory=list)


@dataclass
class DocAudit:
    name: str
    source: str
    chunks: list[ChunkRecord]
    table_item_to_chunks: dict[str, list[int]]


def extract_chunk_records(dl_doc, chunker) -> list[ChunkRecord]:
    """Pull page/bbox-derived page numbers, labels, and headings per chunk
    straight from Docling's own document model — this is the provenance that
    exists internally but is discarded before chunks reach Chroma today."""
    records = []
    for i, chunk in enumerate(chunker.chunk(dl_doc)):
        pages = sorted({prov.page_no for item in chunk.meta.doc_items for prov in item.prov})
        labels = [item.label.value for item in chunk.meta.doc_items]
        refs = [item.self_ref for item in chunk.meta.doc_items]
        headings = list(chunk.meta.headings or [])
        records.append(ChunkRecord(
            index=i,
            text=chunk.text,
            word_count=len(chunk.text.split()),
            pages=pages,
            labels=labels,
            headings=headings,
            doc_item_refs=refs,
        ))
    return records


def flag_records(records: list[ChunkRecord]) -> None:
    """Mutates each record's `flags` in place. Heuristics only — a flag means
    "look at this", not "this is definitely wrong"."""
    max_page_seen = 0
    heading_seen_at_all = any(r.headings for r in records)
    table_item_to_chunks: dict[str, list[int]] = {}

    for r in records:
        if r.pages and max(r.pages) < max_page_seen:
            r.flags.append(
                f"reading-order: page {r.pages} appears after page {max_page_seen} was already seen"
            )
        if r.pages:
            max_page_seen = max(max_page_seen, max(r.pages))

        if r.word_count < SHORT_FRAGMENT_WORDS:
            r.flags.append(f"short-fragment: {r.word_count} words (< {SHORT_FRAGMENT_WORDS})")

        if heading_seen_at_all and not r.headings and "table" not in r.labels:
            r.flags.append("no-heading: other chunks in this doc have section headings, this one doesn't")

        header_footer_labels = {"page_header", "page_footer"}
        if set(r.labels) & header_footer_labels and set(r.labels) - header_footer_labels:
            r.flags.append(f"header-footer-bleed: mixes {r.labels} in one chunk")

        for ref, label in zip(r.doc_item_refs, r.labels):
            if label == "table":
                table_item_to_chunks.setdefault(ref, []).append(r.index)

    for ref, chunk_indices in table_item_to_chunks.items():
        if len(set(chunk_indices)) > 1:
            for idx in chunk_indices:
                records[idx].flags.append(
                    f"table-shredded: table item {ref} split across chunks {sorted(set(chunk_indices))}"
                )


def audit_document(name: str, source: str, converter, chunker) -> DocAudit:
    result = converter.convert(source)
    records = extract_chunk_records(result.document, chunker)
    flag_records(records)
    table_map: dict[str, list[int]] = {}
    for r in records:
        for ref, label in zip(r.doc_item_refs, r.labels):
            if label == "table":
                table_map.setdefault(ref, []).append(r.index)
    return DocAudit(name=name, source=source, chunks=records, table_item_to_chunks=table_map)
