"""Extract full text from parsed data and split into chunks."""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict

def extract_and_chunk_text(parsed_data: Dict, metadata: Dict, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[Dict]:
    full_text = parsed_data.get("full_text", "")
    if not full_text:
        full_text = "\n".join([page.get("content", "") for page in parsed_data.get("pages", [])])
    
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
