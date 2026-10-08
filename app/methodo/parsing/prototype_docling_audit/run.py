"""
PROTOTYPE — throwaway. Runs the audit over the 17-doc sample from
.scratch/docling-parsing-audit/issues/01-parse-vs-source-comparison.md and
caches results to a JSON scratch file for the TUI (view.py) to browse.

Run: docker exec luxdem_backend python3 -m app.methodo.parsing.prototype_docling_audit.run
"""
import dataclasses
import json
import time
from pathlib import Path

from app.methodo.parsing.docling_parser import _chunker, _get_converter
from app.methodo.parsing.prototype_docling_audit.core import audit_document

CACHE_PATH = Path("/app/data/_prototype_docling_audit_cache.json")  # PROTOTYPE — wipe me

DOWNLOADS = Path("/app/data/downloads")

SAMPLE = [
    # (name, local path or None, fetch url or None) — housing-relevant dossiers,
    # confirmed by title against the `dossier` table (see ticket 01).
    ("8532_Depot (aides individuelles au logement)", DOWNLOADS / "8532_Depot.pdf", None),
    ("8532_Resume", DOWNLOADS / "8532_Resume.pdf", None),
    ("8534_Depot (Fonds du Logement)", DOWNLOADS / "8534_Depot.pdf", None),
    ("8548_Depot (Administration aides individuelles)", DOWNLOADS / "8548_Depot.pdf", None),
    ("8008_Depot (indexation loyer, short)", None,
     "https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8008/20250514_Dep%C3%B4t.pdf"),
    ("8080_Depot (budget omnibus, housing is 1 clause)", None,
     "https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8080/20250515_Dep%C3%B4t.pdf"),
    ("8353_Depot (relance marche logement, 4 laws)", None,
     "https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8353/20250801_Depot_2.pdf"),
    ("8589_Depot (Pacte logement communes)", None,
     "https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8589/20260128_Depot.pdf"),
    ("ONH logement-en-chiffre-16 (stat-infographic)", DOWNLOADS / "onh/logement-en-chiffre-16.pdf", None),
    ("ONH logement-en-chiffre-18 (stat-infographic)", DOWNLOADS / "onh/logement-en-chiffre-18-202509.pdf", None),
    ("ONH rapport-analyse-14 (smallest)", DOWNLOADS / "onh/rapport-analyse-14.pdf", None),
    ("ONH rapport-analyse-21 (tables-heavy)", DOWNLOADS / "onh/rapport-analyse-21.pdf", None),
    ("ONH note-41 (large)", DOWNLOADS / "onh/note-41.pdf", None),
    ("ONH note-n39 (largest)", DOWNLOADS / "onh/note-n39.pdf", None),
    ("ONH Note-30 (full report)", DOWNLOADS / "onh/Note-30.pdf", None),
    ("ONH Note-30-en-bref (its own summary)", DOWNLOADS / "onh/Note-30-en-bref.pdf", None),
    ("ONH cahiers-gr-8", DOWNLOADS / "onh/cahiers-gr-8.pdf", None),
    ("Coalition agreement 2023-2028", DOWNLOADS / "accord_coalition_2023_2028.pdf", None),
]


def _ensure_local(name: str, local_path: Path | None, url: str | None) -> Path:
    if local_path is not None:
        if not local_path.exists():
            raise FileNotFoundError(f"{name}: expected local file missing: {local_path}")
        return local_path
    import requests
    fetch_dir = Path("/app/data/_prototype_docling_audit_fetched")  # PROTOTYPE — wipe me
    fetch_dir.mkdir(exist_ok=True)
    dest = fetch_dir / (name.split(" ")[0] + ".pdf")
    if not dest.exists():
        print(f"   fetching {url} -> {dest}")
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def main() -> None:
    converter = _get_converter()
    results = []
    for name, local_path, url in SAMPLE:
        print(f"[{name}] resolving source...")
        path = _ensure_local(name, local_path, url)
        t0 = time.time()
        print(f"[{name}] parsing {path} ...")
        try:
            audit = audit_document(name, str(path), converter, _chunker)
        except Exception as e:
            print(f"[{name}] FAILED: {e}")
            results.append({"name": name, "source": str(path), "error": str(e)})
            continue
        elapsed = round(time.time() - t0, 1)
        n_flagged = sum(1 for c in audit.chunks if c.flags)
        print(f"[{name}] {len(audit.chunks)} chunks, {n_flagged} flagged ({elapsed}s)")
        results.append({
            "name": audit.name,
            "source": audit.source,
            "chunks": [dataclasses.asdict(c) for c in audit.chunks],
        })
        CACHE_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nDone. Cache written to {CACHE_PATH}")


if __name__ == "__main__":
    main()
