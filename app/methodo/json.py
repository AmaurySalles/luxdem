# === Step 3: Normalize and save JSON ===
from datetime import datetime
from pathlib import Path
from typing import List, Dict

#  === Configuration ===
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def save_normalized_json(parsed_data: Dict, pdf_url: str, slug: str) -> Path:
    """Save parsed data and metadata to JSON file."""
    metadata = {
        "source_url": pdf_url,
        "filename": slug,
        "parsed_at": datetime.utcnow().isoformat() + "Z",
        "parser": "reducto.ai"
    }
    
    normalized_data = {
        "metadata": metadata,
        **parsed_data  # Assuming parsed_data is already structured; adjust if needed
    }
    
    out_path = DATA_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(normalized_data, ensure_ascii=False, indent=2))
    print(f"   → Saved normalized JSON: {out_path}")
    return out_path
