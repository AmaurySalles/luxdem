"""Parse PDF using Docling (local, no API)."""

from typing import Any

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from ecodev_core import logger_get

log = logger_get(__name__)

# Singletons — models load once per process
_converter = DocumentConverter()
_chunker = HybridChunker()


def parse_with_docling(source: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a PDF from a URL or local path and return structured chunks."""
    log.info(f'Parsing with Docling: {source}')
    result = _converter.convert(source)
    chunks = list(_chunker.chunk(result.document))
    log.info(f'Docling produced {len(chunks)} chunks')
    return [
        {
            "page_content": chunk.text,
            "metadata": {**metadata, "chunk_index": i, "chunk_count": len(chunks)},
        }
        for i, chunk in enumerate(chunks)
    ]
