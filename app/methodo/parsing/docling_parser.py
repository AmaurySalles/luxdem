"""Parse PDF using Docling (local, no API)."""

from collections import Counter
from typing import Any

import torch
from docling.chunking import HybridChunker
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DocItemLabel
from ecodev_core import SETTINGS, logger_get

log = logger_get(__name__)

_converter: DocumentConverter | None = None
# nomic-embed-text has an 8192-token context; using its tokenizer avoids false
# "sequence too long" warnings from the default BAAI tokenizer (512-token limit).
_chunker = HybridChunker(tokenizer="nomic-ai/nomic-embed-text-v1", max_tokens=512)

# Docling's own heading-level detection (chunk.meta.headings) assigns every
# section_header in the coalition agreement PDF the *same* level, since its
# layout model has no signal distinguishing a chapter title like "Logement"
# from a body sub-header like "Création de logements abordables". We recover
# the two levels ourselves from layout: a chapter title is either centered
# (off the body's left margin) or set in a visibly larger font than the
# common body-header size; anything else at the margin is a sub-header.
_MARGIN_TOLERANCE_PT = 5.0
_HEADER_FONT_BUFFER_PT = 1.0  # chapter-title height must exceed body height by at least this
# A wrapped 2-line body sub-header inflates bbox height to ~2x a single line, which would
# otherwise look "oversized"; caps the oversized-font check to a single text line so it
# doesn't mistake a long wrapped sub-header for a larger-font chapter title.
_HEADER_FONT_MAX_MULTIPLE = 1.8


def _read_docling_config() -> tuple[str, int]:
    docling = getattr(SETTINGS, "docling", None)
    accelerator = getattr(docling, "accelerator", "auto") if docling else "auto"
    num_threads = getattr(docling, "num_threads", 8) if docling else 8
    return accelerator, num_threads


def _resolve_device(name: str) -> AcceleratorDevice:
    if name == "mps":
        if torch.backends.mps.is_available():
            return AcceleratorDevice.MPS
        log.warning("MPS requested but not available; falling back to CPU")
        return AcceleratorDevice.CPU
    if name == "cpu":
        return AcceleratorDevice.CPU
    return AcceleratorDevice.AUTO


def _create_converter() -> DocumentConverter:
    accelerator_name, num_threads = _read_docling_config()
    device = _resolve_device(accelerator_name)
    log.info(f"Docling using accelerator={device.value} (num_threads={num_threads})")
    pipeline_options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device, num_threads=num_threads)
    )
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = _create_converter()
    return _converter


def _is_content_section_header(item: Any, content_start_page: int) -> bool:
    return (
        getattr(item, "label", None) == DocItemLabel.SECTION_HEADER
        and bool(item.prov)
        and item.prov[0].page_no >= content_start_page
    )


def _layout_stats(document: Any, content_start_page: int) -> tuple[float | None, float]:
    """Detect the page's left text margin (most common left-x among
    section_headers — sub-headers sit flush with it, chapter titles don't
    always) and the dominant single-line body-header font height (the taller
    of the two most common heights at that margin; rare, much taller values
    are 2-line wraps, not a real third level).
    """
    lefts: Counter = Counter()
    for item, _ in document.iterate_items():
        if _is_content_section_header(item, content_start_page):
            lefts[round(item.prov[0].bbox.l, 1)] += 1
    if not lefts:
        return None, 0.0
    margin = lefts.most_common(1)[0][0]

    heights: Counter = Counter()
    for item, _ in document.iterate_items():
        if _is_content_section_header(item, content_start_page) and abs(
            item.prov[0].bbox.l - margin
        ) <= _MARGIN_TOLERANCE_PT:
            bbox = item.prov[0].bbox
            heights[round(bbox.t - bbox.b, 1)] += 1
    dominant_body_height = max(h for h, _ in heights.most_common(2)) if heights else 0.0
    return margin, dominant_body_height


def _build_heading_map(
    document: Any, content_start_page: int
) -> dict[str, tuple[str | None, str | None]]:
    """Walk the document in reading order, tracking the current (header,
    subheader) and tagging every item's self_ref with it. A section_header is
    a chapter header — resetting the sub-header — if it's off the body
    margin (centered) or set in a visibly larger font than the common body
    header height; otherwise it's a sub-header (sibling of the previous one).
    Headers before `content_start_page` (e.g. a cover page or table of
    contents, which isn't real document structure) are ignored.
    """
    margin, dominant_body_height = _layout_stats(document, content_start_page)
    oversized_range = (
        dominant_body_height + _HEADER_FONT_BUFFER_PT,
        dominant_body_height * _HEADER_FONT_MAX_MULTIPLE,
    )
    tag_of_ref: dict[str, tuple[str | None, str | None]] = {}
    header, subheader = None, None
    for item, _ in document.iterate_items():
        if _is_content_section_header(item, content_start_page):
            text = item.text.strip()
            bbox = item.prov[0].bbox
            height = bbox.t - bbox.b
            off_margin = margin is None or abs(bbox.l - margin) > _MARGIN_TOLERANCE_PT
            oversized = oversized_range[0] < height <= oversized_range[1]
            if off_margin or oversized:
                header, subheader = text, None
            else:
                subheader = text
        tag_of_ref[item.self_ref] = (header, subheader)
    return tag_of_ref


def _heading_metadata(
    chunk: Any, tag_of_ref: dict[str, tuple[str | None, str | None]]
) -> dict[str, Any]:
    """Look up the (header, subheader) covering a chunk's first source item,
    and flatten it into scalar metadata fields so Chroma's equality `where`
    filters can retrieve all chunks under a given header or sub-header
    deterministically.
    """
    doc_items = getattr(chunk.meta, "doc_items", None) or []
    header, subheader = tag_of_ref.get(doc_items[0].self_ref, (None, None)) if doc_items else (
        None, None
    )
    heading_path = " > ".join(h for h in (header, subheader) if h) or None
    return {"header": header, "subheader": subheader, "heading_path": heading_path}


def parse_with_docling(source: str, metadata: dict[str, Any],
                       min_chunk_words: int | None = None,
                       content_start_page: int = 1) -> list[dict[str, Any]]:
    log.info(f"Parsing with Docling: {source}")
    result = _get_converter().convert(source)
    tag_of_ref = _build_heading_map(result.document, content_start_page)
    chunks = list(_chunker.chunk(result.document))
    log.info(f"Docling produced {len(chunks)} chunks")
    if min_chunk_words is not None:
        kept = [c for c in chunks if len(c.text.split()) >= min_chunk_words]
        dropped = len(chunks) - len(kept)
        if dropped:
            log.info(f"   → dropped {dropped} low-signal chunk(s) (< {min_chunk_words} words)")
    else:
        kept = chunks
    return [
        {
            "page_content": chunk.text,
            "metadata": {
                **metadata,
                **_heading_metadata(chunk, tag_of_ref),
                "chunk_index": i,
                "chunk_count": len(kept),
            },
        }
        for i, chunk in enumerate(kept)
    ]
