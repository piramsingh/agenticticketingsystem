"""
Status endpoint — tells the extension which connector is active and whether it's reachable.
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/status", tags=["status"])

_connector = None
_connector_type: str = "unknown"
_project: str = ""

_DISPLAY: dict = {
    "jira":          {"name": "Jira",          "color": "#0052CC"},
    "azure_devops":  {"name": "Azure DevOps",   "color": "#0078D4"},
    "jama":          {"name": "Jama",           "color": "#E36D00"},
    "github":        {"name": "GitHub Issues",  "color": "#238636"},
    "linear":        {"name": "Linear",         "color": "#5E6AD2"},
}


def set_connector(connector, connector_type: str, project: str) -> None:
    global _connector, _connector_type, _project
    _connector = connector
    _connector_type = connector_type
    _project = project


@router.get("")
async def get_status():
    """Return the active connector type, project, and connection health."""
    meta = _DISPLAY.get(_connector_type, {"name": _connector_type.replace("_", " ").title(), "color": "#888"})

    connected = False
    if _connector:
        try:
            connected = await _connector.validate_connection()
        except Exception:
            connected = False

    return {
        "connector_type": _connector_type,
        "display_name":   meta["name"],
        "color":          meta["color"],
        "project":        _project,
        "connected":      connected,
    }
