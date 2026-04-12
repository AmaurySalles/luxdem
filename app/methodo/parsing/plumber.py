"""Parse PDF using Plumber."""

from typing import Any
from app.methodo.parsing.download import download_pdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pdfplumber
from pathlib import Path

def parse_with_pdfplumber(url: str, metadata: dict[str, Any]) -> dict:
    """Parse PDF using pdfplumber and return structured JSON."""
    print(f"Downloading and parsing PDF with PDF plumber: {url}")
    parsed_str = plumber_parse_from_url(url)
    print(f"Extract text and chunks")
    parsed_chunks = chunk_text(parsed_str, metadata)
    return parsed_chunks

def plumber_parse_from_url(url: str) -> str:
    """Extract text from PDF using pdfplumber."""
    pdf_path = download_pdf(url)
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        print(f"   → Extracting text from {num_pages} pages...")
        
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            full_text += f"\n--- Page {i} ---\n{text}\n"
            
            """ Extract tables if present."""
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    full_text += "\n[TABLE]\n"
                    for row in table:
                        full_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
    
    return full_text.strip()


def chunk_text(full_text: str, metadata: dict, chunk_size: int = 1000, chunk_overlap: int = 100) -> list[dict]:
    """Split text into chunks with metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    text_chunks = splitter.split_text(full_text)

    chunks_with_metadata = [
        {
            "page_content": chunk,
            "metadata": {**metadata, "chunk_index": i, "chunk_count": len(text_chunks)},
        }
        for i, chunk in enumerate(text_chunks)
    ]
    return chunks_with_metadata
