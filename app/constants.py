"""
Global useful constants
"""
from pathlib import Path
from ecodev_core import SETTINGS


APP_NAME = SETTINGS.app_name

"""
PATH VARIABLES
"""
DATA_DIR = Path('/app/data')
ASSETS_DIR = Path('/app/app/assets')
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


