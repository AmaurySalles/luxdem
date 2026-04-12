from sqlmodel import Session, select
from app.db_model.tables import Resource

def retrieve_all_resources(session: Session, 
                          title: str | None = None,
                          limit: int | None = None,
                          ) -> list[Resource]:
    """
    Retrieve all resources by title.
    If title is not provided, retrieve all resources.
    """
    query = select(Resource)
    if title:
        query = query.where(Resource.title == title)
    if limit:
        query = query.limit(limit)

    return session.exec(query).all()
    
    