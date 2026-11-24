"""
Who a dossier's author was when they tabled it (#119): government functions and party,
each with its source, never guessed.
"""
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session

from app.db_model.retrievers.government_retriever import retrieve_commission_group_on
from app.db_model.retrievers.government_retriever import retrieve_mandates_on
from app.db_model.retrievers.government_retriever import retrieve_party_statement
from app.methodo.chd_opendata import COMMISSIONS
from app.methodo.government import MANDATES_URL
from app.methodo.government import split_listed_name

CHD_COMMISSIONS_SOURCE = f"CHD open data, dataset {COMMISSIONS.number}"


@dataclass(frozen=True)
class AuthorProfile:
    name: str
    functions: list[str]  # government functions held on the date; empty for a deputy
    functions_source: str | None
    party: str | None  # None: no source states it
    party_source: str | None


def author_profile(session: Session, author: str, on: date) -> AuthorProfile:
    """
    The author's government functions and party on `on`.

    NOTE: party from the official biography first, else the political group of the
    author's latest CHD commission role.
    """
    last, first = split_listed_name(_upper_last_name(author))
    functions = [m.function for m in retrieve_mandates_on(session, last, first, on)]
    if statement := retrieve_party_statement(session, last, first):
        party, party_source = statement.party, f"{statement.source_url} : « {statement.quote} »"
    elif group := retrieve_commission_group_on(session, last, first, on):
        party, party_source = group, CHD_COMMISSIONS_SOURCE
    else:
        party, party_source = None, None
    return AuthorProfile(name=author, functions=functions,
                         functions_source=MANDATES_URL if functions else None,
                         party=party, party_source=party_source)


def _upper_last_name(author: str) -> str:
    """'Claude MEISCH' from chd.lu's 'Claude Meisch': first names come first, one word."""
    first, _, last = author.partition(" ")
    return f"{first} {last.upper()}"
