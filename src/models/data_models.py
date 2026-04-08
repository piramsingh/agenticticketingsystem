# Shim — re-exports from the new canonical location.
# JamaItem is kept here for backwards compatibility; it no longer lives in the
# new models/ticket.py (which is tool-agnostic). Delete this file once all
# imports are updated to use src.models.ticket directly.
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict

from .ticket import Activity, CreateItemResult, TargetItem, WebhookEvent, PollResult


@dataclass
class JamaItem:
    """
    Jama-specific item model — kept for backwards compatibility with JamaClient.

    New code should use TargetItem (from src.models.ticket) throughout.
    JamaConnector converts JamaItem → TargetItem internally.
    """
    id: int
    project_id: int
    item_type: str
    name: str
    description: str
    status: str
    priority: str
    last_modified: datetime
    fields: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["last_modified"] = self.last_modified.isoformat()
        return data


__all__ = [
    "JamaItem",
    "Activity",
    "CreateItemResult",
    "TargetItem",
    "WebhookEvent",
    "PollResult",
]
