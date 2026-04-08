"""Mock Jama client for demo purposes"""
import asyncio
from datetime import datetime, timedelta
from typing import List

from src.models.data_models import Activity, JamaItem


class MockJamaClient:
    """
    Mock Jama client that returns hardcoded data for demo purposes.
    
    Simulates the real JamaClient interface but with fake data.
    """
    
    def __init__(self, config):
        """Initialize mock client"""
        self.config = config
        self.project_id = config.project_id
        
        # Hardcoded mock data
        self.mock_items = {
            100: JamaItem(
                id=100,
                project_id=self.project_id,
                item_type="Requirement",
                name="User shall be able to login",
                description="The system shall provide a secure login form with username and password fields",
                status="Draft",
                priority="High",
                last_modified=datetime.utcnow() - timedelta(hours=2),
                fields={
                    "name": "User shall be able to login",
                    "description": "The system shall provide a secure login form",
                    "status": "Draft",
                    "priority": "High",
                    "custom_field": "Authentication"
                }
            ),
            101: JamaItem(
                id=101,
                project_id=self.project_id,
                item_type="Requirement",
                name="System shall validate user credentials",
                description="The system shall verify username and password against the database",
                status="Approved",
                priority="High",
                last_modified=datetime.utcnow() - timedelta(hours=1),
                fields={
                    "name": "System shall validate user credentials",
                    "description": "The system shall verify username and password",
                    "status": "Approved",
                    "priority": "High"
                }
            ),
            102: JamaItem(
                id=102,
                project_id=self.project_id,
                item_type="Requirement",
                name="User shall receive error message on invalid login",
                description="The system shall display a clear error message when login fails",
                status="Draft",
                priority="Medium",
                last_modified=datetime.utcnow() - timedelta(minutes=30),
                fields={
                    "name": "User shall receive error message on invalid login",
                    "description": "The system shall display a clear error message",
                    "status": "Draft",
                    "priority": "Medium"
                }
            )
        }
        
        self.call_count = 0
    
    async def get_activities(self, since: datetime) -> List[Activity]:
        """Return mock activities"""
        await asyncio.sleep(0.1)  # Simulate API delay
        
        self.call_count += 1
        
        # Return activities for items created/updated after 'since'
        activities = []
        
        for item_id, item in self.mock_items.items():
            if item.last_modified > since:
                activities.append(Activity(
                    id=1000 + item_id,
                    activity_type="ITEM_UPDATED" if self.call_count > 1 else "ITEM_CREATED",
                    item_id=item_id,
                    timestamp=item.last_modified,
                    user="demo_user"
                ))
        
        print(f"[DEMO] MockJamaClient.get_activities() returned {len(activities)} activities")
        return activities
    
    async def get_item(self, item_id: int) -> JamaItem:
        """Return mock item details"""
        await asyncio.sleep(0.05)  # Simulate API delay
        
        if item_id not in self.mock_items:
            raise ValueError(f"Item {item_id} not found")
        
        item = self.mock_items[item_id]
        print(f"[DEMO] MockJamaClient.get_item({item_id}) returned: {item.name}")
        return item
    
    async def update_item(self, item_id: int, fields: dict) -> None:
        """Simulate updating an item"""
        await asyncio.sleep(0.05)  # Simulate API delay
        
        if item_id not in self.mock_items:
            raise ValueError(f"Item {item_id} not found")
        
        # Update the mock item
        item = self.mock_items[item_id]
        for field, value in fields.items():
            if field == "status":
                item.status = value
            elif field == "priority":
                item.priority = value
            elif field == "description":
                item.description = value
            elif field == "name":
                item.name = value
        
        item.last_modified = datetime.utcnow()
        
        print(f"[DEMO] MockJamaClient.update_item({item_id}) updated fields: {list(fields.keys())}")
