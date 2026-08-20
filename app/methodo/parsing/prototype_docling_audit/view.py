"""
PROTOTYPE — throwaway. TUI to page through the docling-parse audit cache
produced by run.py. Thin shell: all it does is read state and dispatch
keystrokes; no logic here beyond navigation.

Run: docker exec -it luxdem_backend python3 -m app.methodo.parsing.prototype_docling_audit.view
"""
import json
from pathlib import Path

CACHE_PATH = Path("/app/data/_prototype_docling_audit_cache.json")

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
RESET = "\x1b[0m"


def load_docs() -> list[dict]:
    return json.loads(CACHE_PATH.read_text())


def render(docs: list[dict], doc_i: int, flagged_only: bool, chunk_i: int) -> None:
    print("\033[2J\033[H", end="")
    doc = docs[doc_i]
    print(f"{BOLD}[{doc_i + 1}/{len(docs)}] {doc['name']}{RESET}")
    print(f"{DIM}{doc.get('source', '')}{RESET}\n")

    if "error" in doc:
        print(f"{RED}FAILED: {doc['error']}{RESET}")
    else:
        chunks = doc["chunks"]
        n_flagged = sum(1 for c in chunks if c["flags"])
        print(f"{BOLD}{len(chunks)} chunks total, {n_flagged} flagged{RESET}"
              f"  {DIM}(showing: {'flagged only' if flagged_only else 'all'}){RESET}\n")

        visible = [c for c in chunks if (c["flags"] or not flagged_only)]
        if not visible:
            print(f"{DIM}(nothing to show){RESET}")
        else:
            chunk_i = chunk_i % len(visible)
            c = visible[chunk_i]
            print(f"{BOLD}chunk #{c['index']}{RESET}  "
                  f"{DIM}pages={c['pages']} labels={c['labels']} headings={c['headings']}{RESET}")
            if c["flags"]:
                for f in c["flags"]:
                    print(f"  {RED}⚑ {f}{RESET}")
            else:
                print(f"  {DIM}(no flags){RESET}")
            print(f"\n{c['text'][:800]}{'...' if len(c['text']) > 800 else ''}\n")
            print(f"{DIM}[{chunk_i + 1}/{len(visible)} in this view]{RESET}")

    print(f"\n{BOLD}[n]{RESET}{DIM} next doc {RESET} "
          f"{BOLD}[p]{RESET}{DIM} prev doc {RESET} "
          f"{BOLD}[j]{RESET}{DIM} next chunk {RESET} "
          f"{BOLD}[k]{RESET}{DIM} prev chunk {RESET} "
          f"{BOLD}[f]{RESET}{DIM} toggle flagged-only {RESET} "
          f"{BOLD}[q]{RESET}{DIM} quit{RESET}")


def main() -> None:
    docs = load_docs()
    doc_i, chunk_i, flagged_only = 0, 0, True
    render(docs, doc_i, flagged_only, chunk_i)
    while True:
        key = input("> ").strip().lower()
        if key == "q":
            break
        elif key == "n":
            doc_i = (doc_i + 1) % len(docs)
            chunk_i = 0
        elif key == "p":
            doc_i = (doc_i - 1) % len(docs)
            chunk_i = 0
        elif key == "j":
            chunk_i += 1
        elif key == "k":
            chunk_i -= 1
        elif key == "f":
            flagged_only = not flagged_only
            chunk_i = 0
        render(docs, doc_i, flagged_only, chunk_i)


if __name__ == "__main__":
    main()
