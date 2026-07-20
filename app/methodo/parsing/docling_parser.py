"""Parse PDF using Docling (local, no API)."""

from typing import Any

import torch
from docling.chunking import HybridChunker
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from ecodev_core import SETTINGS, logger_get

log = logger_get(__name__)

_converter: DocumentConverter | None = None
# nomic-embed-text has an 8192-token context; using its tokenizer avoids false
# "sequence too long" warnings from the default BAAI tokenizer (512-token limit).
_chunker = HybridChunker(tokenizer="nomic-ai/nomic-embed-text-v1", max_tokens=512)


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


def parse_with_docling(source: str, metadata: dict[str, Any],
                       min_chunk_words: int | None = None) -> list[dict[str, Any]]:
    log.info(f"Parsing with Docling: {source}")
    result = _get_converter().convert(source)
    chunks = list(_chunker.chunk(result.document))
    log.info(f"Docling produced {len(chunks)} chunks")
    if min_chunk_words is not None:
        texts = [c.text for c in chunks if len(c.text.split()) >= min_chunk_words]
        dropped = len(chunks) - len(texts)
        if dropped:
            log.info(f"   → dropped {dropped} low-signal chunk(s) (< {min_chunk_words} words)")
    else:
        texts = [c.text for c in chunks]
    return [
        {
            "page_content": text,
            "metadata": {**metadata, "chunk_index": i, "chunk_count": len(texts)},
        }
        for i, text in enumerate(texts)
    ]
