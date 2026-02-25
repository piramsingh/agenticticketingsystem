"""Shared data models for sync operations"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any


@dataclass
class JamaItem:
    """
    Represents a Jama Connect item (requirement, test case, etc.)
    
    Attributes:
        id: Jama item ID
        project_id: Jama project ID
        item_type: Type of item (e.g., "Requirement", "Test Case")
        name: Item name/title
        description: Item description
        status: Current status
        priority: Priority level
        last_modified: Last modification timestamp
        fields: Additional custom fields
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
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['last_modified'] = self.last_modified.isoformat()
        return data


@dataclass
class Activity:
    """
    Represents a Jama activity stream event
    
    Attributes:
        id: Activity ID
        activity_type: Type of activity (ITEM_CREATED, ITEM_UPDATED, etc.)
        item_id: ID of the item that was modified
        timestamp: When the activity occurred
        user: User who performed the action
    """
    id: int
    activity_type: str
    item_id: int
    timestamp: datetime
    user: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class CreateItemResult:
    """
    Result of creating an item in a target tool
    
    Attributes:
        item_id: ID of the created item
        item_url: URL to view the item
        created_at: When the item was created
    """
    item_id: str
    item_url: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class TargetItem:
    """
    Represents an item in a target tool (Azure DevOps, GitLab, Jira)
    
    Attributes:
        item_id: Target tool item ID
        title: Item title
        description: Item description
        status: Current status
        priority: Priority level
        last_modified: Last modification timestamp
        fields: Additional custom fields
    """
    item_id: str
    title: str
    description: str
    status: str
    priority: str
    last_modified: datetime
    fields: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['last_modified'] = self.last_modified.isoformat()
        return data


@dataclass
class WebhookEvent:
    """
    Standardized webhook event from target tools
    
    Attributes:
        event_type: Type of event (created, updated, deleted)
        item_id: ID of the item that changed
        updated_fields: Fields that were updated
        timestamp: When the event occurred
    """
    event_type: str
    item_id: str
    updated_fields: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class PollResult:
    """
    Result of a Jama polling operation
    
    Attributes:
        success: Whether the poll was successful
        items_processed: Number of items processed
        error: Error message if poll failed
    """
    success: bool
    items_processed: int = 0
    error: str | None = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
