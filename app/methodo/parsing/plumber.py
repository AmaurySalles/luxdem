# === Step 2: Parse PDF with pdfplumber ===
import pdfplumber
from pathlib import Path

def parse_pdf_with_pdfplumber(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
    full_text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        print(f"   → Extracting text from {num_pages} pages...")
        
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            full_text += f"\n--- Page {i} ---\n{text}\n"
            
            # Extract tables if present
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    full_text += "\n[TABLE]\n"
                    for row in table:
                        full_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
    
    return full_text.strip()