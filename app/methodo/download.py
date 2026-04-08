# === Step 1: Download PDF ===
from pathlib import Path
import requests

# === Configuration ===
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


def download_pdf(pdf_url: str) -> Path:
    """Download PDF from URL and save locally."""
    filename = pdf_url.split("/")[-1]
    dest = DOWNLOADS_DIR / filename
    
    if dest.exists():
        print(f"   → PDF already downloaded: {dest}")
        return dest
    
    print(f"   → Downloading {filename}...")
    response = requests.get(pdf_url, timeout=30, verify=False)
    response.raise_for_status()
    dest.write_bytes(response.content)
    print(f"   → Saved to {dest}")
    return dest
