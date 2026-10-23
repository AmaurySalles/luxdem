"""
Write operations on ONH publications.
"""
from sqlmodel import Session

from app.db_model.tables.onh_publication import OnhPublication


def update_onh_publication_urls(session: Session, new_urls: dict[int, str]) -> int:
    """Set `url` for each publication id in one transaction. Returns the number updated."""
    updated = 0
    for pub_id, url in new_urls.items():
        pub = session.get(OnhPublication, pub_id)
        if pub is None:
            continue
        pub.url = url
        session.add(pub)
        updated += 1
    session.commit()
    return updated
