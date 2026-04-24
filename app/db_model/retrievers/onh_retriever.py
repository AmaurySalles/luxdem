from sqlmodel import Session, select

from app.db_model.tables.onh_publication import OntPublication
from app.db_model.tables.onh_summary import OntSummary


def retrieve_onh_publications(session: Session, limit: int | None = None) -> list[OntPublication]:
    query = select(OntPublication)
    if limit:
        query = query.limit(limit)
    return list(session.exec(query).all())


def retrieve_onh_publication_by_url(session: Session, url: str) -> OntPublication | None:
    query = select(OntPublication).where(OntPublication.url == url)
    return session.exec(query).first()


def upsert_onh_publication(session: Session, publication: OntPublication) -> OntPublication:
    existing = retrieve_onh_publication_by_url(session, publication.url)
    if existing:
        return existing
    session.add(publication)
    session.commit()
    session.refresh(publication)
    return publication


def retrieve_onh_summary(session: Session, onh_id: int) -> OntSummary | None:
    query = select(OntSummary).where(OntSummary.onh_id == onh_id)
    return session.exec(query).first()


def persist_onh_summary(session: Session, onh_id: int, summary: str, model_used: str) -> OntSummary:
    record = OntSummary(onh_id=onh_id, summary=summary, model_used=model_used)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
