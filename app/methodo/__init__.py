"""
Module listing all public method from the methodo modules
"""

from app.methodo.parsing.download import download_pdf
from app.methodo.parsing.plumber import parse_with_pdfplumber
from app.methodo.parsing.reducto import parse_with_reducto
from app.methodo.chroma import get_create_chroma_vectorstore
from app.methodo.ollama import verify_ollama_running
from app.methodo.main_pipeline import dossier_pipeline


__all__ = [
    'download_pdf',
    'parse_with_pdfplumber',
    'parse_with_reducto',
    'get_create_chroma_vectorstore',
    'verify_ollama_running',
    'dossier_pipeline'
]
