"""Get metadata for resource chunk."""

from typing import Any
from app.db_model.tables.resource import Resource

def get_resource_metadata(resource: Resource) -> dict[str, Any]:
    if resource.dossier is None:
        raise ValueError("Resource has no dossier")
    
    return {
        "number": resource.dossier.number,
        "title": resource.dossier.title,
        "summary": resource.dossier.content,
        "authors": resource.dossier.authors,
        "deposit_date": resource.dossier.deposit_date,
        "evacuation_date": resource.dossier.evacuation_date,
        "status": resource.dossier.status,
        "type": resource.dossier.type,
        "source_url": resource.url,
    }
