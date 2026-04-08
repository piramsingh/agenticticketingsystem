"""
Shared data models for ticket creation and sync operations.

These are tool-agnostic dataclasses used across connectors, the agent,
and the sync engine. No tool-specific fields live here.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Activity:
    """
    Represents a change event from a source connector's activity stream.

    Attributes:
        id: Activity ID from the source tool
        activity_type: Type of change (ITEM_CREATED, ITEM_UPDATED, etc.)
        item_id: ID of the item that changed
        timestamp: When the change occurred
        user: Who made the change
    """
    id: int
    activity_type: str
    item_id: int
    timestamp: datetime
    user: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class CreateItemResult:
    """
    Result returned after successfully creating an item in any target tool.

    Attributes:
        item_id: The new item's ID (string so it works for Jira keys like "PROJ-42")
        item_url: Direct URL to view the item
        created_at: Creation timestamp
    """
    item_id: str
    item_url: str
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class TargetItem:
    """
    Represents the current state of an item retrieved from any tool.

    Attributes:
        item_id: Tool-native item ID
        title: Item title / summary
        description: Item description (plain text)
        status: Current workflow status
        priority: Priority label (as a string, canonical)
        last_modified: When the item was last changed
        fields: Full raw field dict from the tool's API response
    """
    item_id: str
    title: str
    description: str
    status: str
    priority: str
    last_modified: datetime
    fields: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['last_modified'] = self.last_modified.isoformat()
        return data


@dataclass
class WebhookEvent:
    """
    A standardized webhook event parsed from any tool's raw payload.

    Attributes:
        event_type: One of "created", "updated", "deleted"
        item_id: ID of the item that changed
        updated_fields: Canonical field dict of what changed (title, status, etc.)
        timestamp: When the event occurred
    """
    event_type: str
    item_id: str
    updated_fields: Dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class PollResult:
    """
    Result of one polling cycle from a source connector.

    Attributes:
        success: Whether the poll completed without fatal error
        items_processed: Number of activity events handled
        error: Error message if the poll failed
    """
    success: bool
    items_processed: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
