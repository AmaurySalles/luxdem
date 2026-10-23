"""
Global useful constants
"""
import os
from pathlib import Path
from ecodev_core import SETTINGS


APP_NAME = SETTINGS.app_name

"""
PATH VARIABLES
"""
_base = Path(os.environ.get("base_path", "/app"))
DATA_DIR = _base / "data"
ASSETS_DIR = _base / "app" / "assets"
# Chroma store, from config `chroma` (defaults: the pre-#51 store). The re-embed (#32) points
# it at a new directory/collection; never write vectors from two clients/models to one collection.
_chroma = getattr(SETTINGS, "chroma", None)
CHROMA_DIR = DATA_DIR / str(getattr(_chroma, "directory", "embeddings"))
CHROMA_COLLECTION = str(getattr(_chroma, "collection", "dossier_docs"))

"""
MAIN URL CONSTANTS
"""
MAIN_PAGE_URL = '/'
FASTAPI_URL = os.environ.get("FASTAPI_URL", "http://127.0.0.1:8025").rstrip("/")

"""
LINKS CONSTANTS
"""
COMM_CHANNEL_URL = 'https://ecosia.com'
FEEDBACK_URL = 'https://ecosia.com'
DOCUMENTATION_URL = 'https://ecosia.com'


