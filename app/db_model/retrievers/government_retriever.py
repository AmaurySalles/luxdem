"""
Read-only queries on government members and dossier authors (#119).
"""
from datetime import date

from sqlmodel import Session
from sqlmodel import or_
from sqlmodel import select

from app.db_model.tables.chd_opendata import CommissionMembership
from app.db_model.tables.chd_opendata import Deputy
from app.db_model.tables.dossier import Dossier
from app.db_model.tables.dossier_page import DossierCommission
from app.db_model.tables.government import GovernmentMandate
from app.db_model.tables.government import PartyStatement


def retrieve_mandates_on(session: Session, last_name: str, first_name: str,
                         day: date) -> list[GovernmentMandate]:
    """Functions this person held in government on `day`."""
    query = select(GovernmentMandate).where(
        GovernmentMandate.last_name == last_name, GovernmentMandate.first_name == first_name,
        GovernmentMandate.start <= day,
        or_(GovernmentMandate.end.is_(None), GovernmentMandate.end >= day))
    return list(session.exec(query).all())


def retrieve_party_statement(session: Session, last_name: str,
                             first_name: str) -> PartyStatement | None:
    query = select(PartyStatement).where(PartyStatement.last_name == last_name,
                                         PartyStatement.first_name == first_name)
    return session.exec(query).first()


def retrieve_commission_group_on(session: Session, last_name: str, first_name: str,
                                 day: date) -> str | None:
    """
    Political group of a deputy's latest commission role started by `day` (CHD dataset 104).

    Purpose: party of an author who sat in the Chambre, at the date of their act.
    """
    query = (select(CommissionMembership.political_group)
             .join(Deputy, Deputy.id == CommissionMembership.deputy_id)
             .where(Deputy.last_name == last_name, Deputy.first_name == first_name,
                    CommissionMembership.role_start <= day,
                    CommissionMembership.political_group != "null")
             .order_by(CommissionMembership.role_start.desc()))
    return session.exec(query).first()


def retrieve_dossiers_by_author_and_commission(session: Session, author: str,
                                               commission_prefix: str) -> list[Dossier]:
    """
    Dossiers whose author field is `author` and that a commission titled `commission_prefix...`
    examined, by number.

    Purpose: a minister's laws in one policy area, e.g. Meisch's housing laws (Commission du
    Logement): the examining commission is a fact from chd.lu, not a model's classification.
    """
    query = (select(Dossier).join(DossierCommission, DossierCommission.dossier_id == Dossier.id)
             .where(Dossier.authors == author,
                    DossierCommission.commission_title.startswith(commission_prefix))
             .distinct().order_by(Dossier.number))
    return list(session.exec(query).all())
