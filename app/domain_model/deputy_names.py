"""
Matching deputy names across CHD sources, which order and spell them differently:
open data ('Arendt', 'Nancy'), vote bulletins ('Arendt épouse Kemp Nancy') and dossier pages
('Franz Fayot').
"""
import unicodedata

# Luxembourgish first names bulletins print instead of the civil one in open data
_FIRST_NAME_VARIANTS = {"charles": {"charel"}}


def normalize_name(name: str) -> str:
    """Casefolded, accent-free, single-spaced: 'Étienne  Schneider' -> 'etienne schneider'."""
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(stripped.casefold().replace("-", " ").split())


def is_same_person(full_name: str, last_name: str, first_name: str) -> bool:
    """
    True when `full_name` is 'Last ... First' or 'First ... Last' for this deputy.

    NOTE: the middle may hold a married name ('Arendt épouse Kemp Nancy').
    """
    full, last, first = (normalize_name(n) for n in (full_name, last_name, first_name))
    return any((full.startswith(f"{last} ") and full.endswith(f" {form}"))
               or (full.startswith(f"{form} ") and full.endswith(f" {last}"))
               for form in {first} | _FIRST_NAME_VARIANTS.get(first, set()))
