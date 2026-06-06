from sqlmodel import Session, select

from app.db_model.tables.onh_publication import OnhPublication
from app.db_model.tables.onh_summary import OnhSummary


def retrieve_onh_publications(session: Session, limit: int | None = None) -> list[OnhPublication]:
    query = select(OnhPublication).order_by(OnhPublication.id.desc())
    if limit:
        query = query.limit(limit)
    return list(session.exec(query).all())


def retrieve_onh_publication_by_url(session: Session, url: str) -> OnhPublication | None:
    query = select(OnhPublication).where(OnhPublication.url == url)
    return session.exec(query).first()


def upsert_onh_publication(session: Session, publication: OnhPublication) -> OnhPublication:
    existing = retrieve_onh_publication_by_url(session, publication.url)
    if existing:
        return existing
    session.add(publication)
    session.commit()
    session.refresh(publication)
    return publication


def retrieve_onh_summary(session: Session, onh_id: int) -> OnhSummary | None:
    query = select(OnhSummary).where(OnhSummary.onh_id == onh_id)
    return session.exec(query).first()


def persist_onh_summary(session: Session, onh_id: int, summary: str, model_used: str) -> OnhSummary:
    record = OnhSummary(onh_id=onh_id, summary=summary, model_used=model_used)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
