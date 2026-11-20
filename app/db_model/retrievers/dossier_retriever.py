from datetime import datetime
from datetime import timezone

from sqlmodel import Session, select

from app.db_model.tables.dossier import Dossier
from app.db_model.tables.dossier_summary import DossierSummary


def retrieve_dossiers_by_numbers(session: Session, numbers: list[str]) -> list[Dossier]:
    query = select(Dossier).where(Dossier.number.in_(numbers))
    return list(session.exec(query).all())


def retrieve_dossier_summary(session: Session, dossier_id: int) -> DossierSummary | None:
    query = select(DossierSummary).where(DossierSummary.dossier_id == dossier_id)
    return session.exec(query).first()


def persist_dossier_summary(session: Session, dossier_id: int, summary: str, model_used: str) -> DossierSummary:
    # Replaces a stale summary (other model or digest): one row per document.
    record = retrieve_dossier_summary(session, dossier_id) or DossierSummary(dossier_id=dossier_id)
    record.summary = summary
    record.model_used = model_used
    record.generated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
