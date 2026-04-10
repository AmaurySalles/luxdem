"""Compatibility shim for legacy imports.

This project now uses provider-agnostic embeddings in app.methodo.embeddings.
"""

from app.methodo.embeddings import get_embedding_function, verify_embedding_provider


def get_ollama_embeddings():
    return get_embedding_function()


def verify_ollama_running() -> bool:
    return verify_embedding_provider()
