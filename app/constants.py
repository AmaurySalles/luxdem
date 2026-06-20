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
EMBEDDINGS_DIR = DATA_DIR / "embeddings"

"""
MAIN URL CONSTANTS
"""
MAIN_PAGE_URL = '/'

"""
LINKS CONSTANTS
"""
COMM_CHANNEL_URL = 'https://ecosia.com'
FEEDBACK_URL = 'https://ecosia.com'
DOCUMENTATION_URL = 'https://ecosia.com'


