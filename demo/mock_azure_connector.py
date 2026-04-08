"""Mock Azure DevOps connector for demo purposes"""
import asyncio
from datetime import datetime
from typing import Dict, Any

from src.clients.connectors.base import BaseConnector
from src.models.data_models import CreateItemResult, TargetItem, WebhookEvent


class MockAzureDevOpsConnector(BaseConnector):
    """
    Mock Azure DevOps connector that simulates API calls with fake data.
    
    Simulates the real AzureDevOpsConnector interface but with in-memory storage.
    """
    
    def __init__(self, config):
        """Initialize mock connector"""
        self.config = config
        self.base_url = config.base_url
        self.project = config.project
        
        # In-memory storage for created items
        self.items: Dict[str, TargetItem] = {}
        self.next_id = 1000
    
    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """Simulate creating a work item"""
        await asyncio.sleep(0.1)  # Simulate API delay
        
        item_id = str(self.next_id)
        self.next_id += 1
        
        # Create mock item
        item = TargetItem(
            item_id=item_id,
            title=fields.get("title", ""),
            description=fields.get("description", ""),
            status=fields.get("state", "New"),
            priority=str(fields.get("priority", "")),
            last_modified=datetime.utcnow(),
            fields=fields
        )
        
        self.items[item_id] = item
        
        result = CreateItemResult(
            item_id=item_id,
            item_url=f"{self.base_url}/{self.project}/_workitems/edit/{item_id}",
            created_at=datetime.utcnow()
        )
        
        print(f"[DEMO] MockAzureDevOpsConnector.create_item() created item {item_id}: {item.title}")
        return result
    
    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """Simulate updating a work item"""
        await asyncio.sleep(0.05)  # Simulate API delay
        
        if item_id not in self.items:
            raise ValueError(f"Item {item_id} not found")
        
        item = self.items[item_id]
        
        # Update fields
        if "title" in fields:
            item.title = fields["title"]
        if "description" in fields:
            item.description = fields["description"]
        if "state" in fields:
            item.status = fields["state"]
        if "priority" in fields:
            item.priority = str(fields["priority"])
        
        item.last_modified = datetime.utcnow()
        item.fields.update(fields)
        
        print(f"[DEMO] MockAzureDevOpsConnector.update_item({item_id}) updated fields: {list(fields.keys())}")
    
    async def get_item(self, item_id: str) -> TargetItem:
        """Simulate retrieving a work item"""
        await asyncio.sleep(0.05)  # Simulate API delay
        
        if item_id not in self.items:
            raise ValueError(f"Item {item_id} not found")
        
        item = self.items[item_id]
        print(f"[DEMO] MockAzureDevOpsConnector.get_item({item_id}) returned: {item.title}")
        return item
    
    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Simulate parsing a webhook payload"""
        # Simple mock webhook parsing
        event_type = payload.get("eventType", "workitem.updated")
        
        if event_type == "workitem.created":
            event_type_normalized = "created"
        elif event_type == "workitem.updated":
            event_type_normalized = "updated"
        else:
            event_type_normalized = "updated"
        
        resource = payload.get("resource", {})
        item_id = str(resource.get("id", ""))
        fields = resource.get("fields", {})
        
        updated_fields = {}
        if "System.Title" in fields:
            updated_fields["title"] = fields["System.Title"]
        if "System.State" in fields:
            updated_fields["state"] = fields["System.State"]
        if "System.Description" in fields:
            updated_fields["description"] = fields["System.Description"]
        
        event = WebhookEvent(
            event_type=event_type_normalized,
            item_id=item_id,
            updated_fields=updated_fields,
            timestamp=datetime.utcnow()
        )
        
        print(f"[DEMO] MockAzureDevOpsConnector.parse_webhook() parsed event: {event_type_normalized} for item {item_id}")
        return event
    
    async def validate_connection(self) -> bool:
        """Simulate connection validation"""
        await asyncio.sleep(0.05)
        print(f"[DEMO] MockAzureDevOpsConnector.validate_connection() returned True")
        return True
