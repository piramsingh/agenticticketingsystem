"""Base connector abstract class for target tool integrations"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from ...models.data_models import CreateItemResult, TargetItem, WebhookEvent


class BaseConnector(ABC):
    """
    Abstract base class for target tool connectors.
    
    This class defines the interface that all target tool connectors must implement
    to support bidirectional synchronization with Jama Connect.
    """
    
    @abstractmethod
    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """
        Create a new work item in the target tool.
        
        Args:
            fields: Dictionary of field values to set on the new item.
                   Keys should match the target tool's field names.
        
        Returns:
            CreateItemResult containing the new item's ID, URL, and creation timestamp.
        
        Raises:
            Exception: If item creation fails.
        """
        pass
    
    @abstractmethod
    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """
        Update an existing work item in the target tool.
        
        Args:
            item_id: ID of the item to update.
            fields: Dictionary of field values to update.
        
        Raises:
            Exception: If item update fails.
        """
        pass
    
    @abstractmethod
    async def get_item(self, item_id: str) -> TargetItem:
        """
        Retrieve work item details from the target tool.
        
        Args:
            item_id: ID of the item to retrieve.
        
        Returns:
            TargetItem containing the item's current state.
        
        Raises:
            Exception: If item retrieval fails or item not found.
        """
        pass
    
    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Parse a webhook payload from the target tool into a standardized event.
        
        Args:
            payload: Raw webhook payload from the target tool.
        
        Returns:
            WebhookEvent with standardized event data.
        
        Raises:
            Exception: If payload parsing fails.
        """
        pass
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Test connectivity to the target tool API.
        
        Returns:
            True if connection is successful, False otherwise.
        """
        pass
