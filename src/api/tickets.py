"""
Tickets API — used by the VS Code extension and web UI.

GET /tickets          — list recent tickets
GET /tickets/{id}     — get a single ticket by ID
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])

# Set by main.py after the connector is built
_connector = None


def set_connector(connector) -> None:
    global _connector
    _connector = connector


@router.get("", response_model=List[dict])
async def list_tickets(limit: int = Query(default=10, le=50)):
    """Return the most recently modified tickets."""
    if not _connector:
        return []
    try:
        return await _connector.list_items(limit)
    except Exception as e:
        logger.error("list_tickets failed: %s", e)
        return []


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Return a single ticket by ID or key."""
    if not _connector:
        raise HTTPException(status_code=503, detail="Connector not initialised")
    try:
        item = await _connector.get_item(ticket_id)
        return {
            "id":           item.item_id,
            "title":        item.title,
            "status":       item.status,
            "priority":     item.priority,
            "description":  item.description,
            "assignedTo":   item.fields.get("System.AssignedTo", {}).get("displayName", "Unassigned")
                            if isinstance(item.fields.get("System.AssignedTo"), dict)
                            else item.fields.get("System.AssignedTo", "Unassigned"),
            "url":          item.fields.get("_links", {}).get("html", {}).get("href", ""),
            "last_modified": item.last_modified.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
