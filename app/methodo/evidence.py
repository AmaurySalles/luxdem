"""
Evidence retrieval for summaries and verdicts (#101): verbatim passages with stable ids.

- Search is grouped by document: one long law can't fill every slot (all 10 chunks of
  "mobilisation des terrains à bâtir" came from 8082, #100).
- Each passage has an id the verdict cites (`dossier/8589#42`, `onh/note-38.pdf#3`,
  `coalition#120`); `find_citations` checks a verdict's citations against the passages it saw.
"""
import re
from enum import Enum
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from pydantic import BaseModel

FETCH_K = 100  # chunks per doc type before grouping: 50 gave only 5 laws for building land (#100)
PASSAGES_PER_DOC = 4
# Summaries are cached once per document, so they focus on the beta's scope (housing, #100)
# rather than on one topic.
SUMMARY_FOCUS_QUERY = ("politique du logement : logements abordables, terrains à bâtir et "
                       "aménagement du territoire, aides au logement, loyers et "
                       "fiscalité immobilière")
_CITATION = re.compile(r"\[([^\[\]]*#\d+[^\[\]]*)\]")


class DocType(Enum):
    DOSSIER = "dossier"
    ONH = "onh"
    COALITION = "coalition"


class Passage(BaseModel):
    id: str
    text: str


class DocEvidence(BaseModel):
    key: str
    metadata: dict[str, Any]
    passages: list[Passage]


def doc_key(metadata: dict[str, Any]) -> str:
    """Document key of a chunk: `dossier/<number>`, `onh/<file>` or `coalition`."""
    doc_type = DocType(metadata["doc_type"])
    if doc_type is DocType.DOSSIER:
        return f"dossier/{metadata['number']}"
    if doc_type is DocType.ONH:
        # pre-fix chunks carry absolute file:// urls, post-fix ones `onh/<file>`
        return f"onh/{Path(metadata['source_url']).name}"
    return doc_type.value


def to_passage(text: str, metadata: dict[str, Any]) -> Passage:
    return Passage(id=f"{doc_key(metadata)}#{metadata['chunk_index']}", text=text)


def retrieve_documents(vectorstore: Chroma, query: str, doc_type: DocType, n_docs: int,
                       passages_per_doc: int = PASSAGES_PER_DOC,
                       fetch_k: int = FETCH_K) -> list[DocEvidence]:
    """Top `n_docs` distinct documents for `query`, each with its best passages, in rank order."""
    hits = vectorstore.similarity_search(query, k=fetch_k, filter={"doc_type": doc_type.value})
    docs: dict[str, DocEvidence] = {}
    for hit in hits:
        key = doc_key(hit.metadata)
        if key not in docs:
            if len(docs) == n_docs:
                continue
            docs[key] = DocEvidence(key=key, metadata=hit.metadata, passages=[])
        if len(docs[key].passages) < passages_per_doc:
            docs[key].passages.append(to_passage(hit.page_content, hit.metadata))
    return list(docs.values())


def retrieve_passages(vectorstore: Chroma, query: str, doc_type: DocType, k: int) -> list[Passage]:
    hits = vectorstore.similarity_search(query, k=k, filter={"doc_type": doc_type.value})
    return [to_passage(hit.page_content, hit.metadata) for hit in hits]


def find_citations(text: str) -> list[str]:
    """Passage ids cited as `[id]` or `[id1; id2]` in `text`, in order of appearance."""
    return [part.strip() for group in _CITATION.findall(text)
            for part in re.split(r"[;,]", group) if "#" in part]
