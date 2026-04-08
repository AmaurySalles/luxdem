# === Step 2: Parse PDF with Reducto API ===
import os
import requests
from pathlib import Path
from reducto import Reducto

# The client reads REDUCTO_API_KEY from your environment
client = Reducto()

#  === Configuration ===
REDUCTO_API_KEY = os.getenv("REDUCTO_API_KEY", "your_api_key_here")
REDUCTO_API_URL = "https://reducto.ai/api/v1/parse"  # Example endpoint; adjust based on actual API


def parse_pdf_with_reducto(pdf_path: Path) -> dict:
    """Parse PDF using Reducto API and return structured JSON."""
    print(f"   → Uploading PDF to Reducto API for parsing...")
    
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        headers = {'Authorization': f'Bearer {REDUCTO_API_KEY}'}
        response = requests.post(REDUCTO_API_URL, files=files, headers=headers, timeout=60, verify=False)
    
    response.raise_for_status()
    parsed_data = response.json()
    print(f"   → Parsed PDF into JSON structure")
    return parsed_data
