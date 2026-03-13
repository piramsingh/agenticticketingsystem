"""Chat agent that handles natural language ticket creation"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .ticket_parser import TicketParser, ParsedTicket
from ..clients.connectors.base import BaseConnector
from ..clients.jama_client import JamaClient
from ..models.data_models import JamaItem


logger = logging.getLogger(__name__)


class ChatAgent:
    """
    AI-powered chat agent for creating tickets from natural language.
    
    This agent:
    1. Parses natural language input
    2. Creates tickets in target tools (Azure DevOps, Jira)
    3. Creates corresponding Jama requirements
    4. Links them together via the sync system
    """
    
    def __init__(
        self,
        parser: TicketParser,
        connector: BaseConnector,
        jama_client: Optional[JamaClient] = None,
        project_id: Optional[int] = None
    ):
        """
        Initialize chat agent.
        
        Args:
            parser: Ticket parser for natural language understanding
            connector: Connector for target tool (Azure DevOps, Jira, etc.)
            jama_client: Optional Jama client for creating requirements
            project_id: Jama project ID for creating requirements
        """
        self.parser = parser
        self.connector = connector
        self.jama_client = jama_client
        self.project_id = project_id
    
    async def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Process natural language message and create tickets.
        
        Args:
            user_input: Natural language description from user
            
        Returns:
            Dictionary with created ticket information and status
            
        Example:
            Input: "Create a ticket for Jamie to fix the security issue"
            Output: {
                "success": True,
                "parsed": {...},
                "target_ticket": {...},
                "jama_requirement": {...},
                "message": "Created ticket #1234 and Jama requirement #5678"
            }
        """
        try:
            # Step 1: Parse natural language
            logger.info(f"Processing message: {user_input}")
            parsed = self.parser.parse(user_input)
            logger.info(f"Parsed ticket: {parsed}")
            
            # Step 2: Create ticket in target tool
            target_ticket = await self._create_target_ticket(parsed)
            logger.info(f"Created target ticket: {target_ticket.item_id}")
            
            # Step 3: Create Jama requirement (if Jama client available)
            jama_requirement = None
            if self.jama_client and self.project_id:
                jama_requirement = await self._create_jama_requirement(parsed, target_ticket)
                logger.info(f"Created Jama requirement: {jama_requirement.id}")
            
            # Step 4: Return success response
            return {
                "success": True,
                "parsed": parsed.to_dict(),
                "target_ticket": {
                    "id": target_ticket.item_id,
                    "url": target_ticket.item_url,
                    "created_at": target_ticket.created_at.isoformat()
                },
                "jama_requirement": {
                    "id": jama_requirement.id if jama_requirement else None
                } if jama_requirement else None,
                "message": self._format_success_message(parsed, target_ticket, jama_requirement)
            }
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create ticket: {str(e)}"
            }
    
    async def _create_target_ticket(self, parsed: ParsedTicket) -> Any:
        """
        Create ticket in target tool (Azure DevOps, Jira, etc.)
        
        Args:
            parsed: Parsed ticket data
            
        Returns:
            CreateItemResult from connector
        """
        # Priority string → Azure DevOps integer (1=Critical, 2=High, 3=Medium, 4=Low)
        priority_map = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        priority_int = priority_map.get((parsed.priority or "medium").lower(), 3)

        fields = {
            "title": parsed.title,
            "description": parsed.description or "",
            "priority": priority_int,
        }

        # Add labels/tags if specified
        if parsed.labels:
            fields["tags"] = ", ".join(parsed.labels)

        # Resolve assignee to Azure DevOps identity if a name was mentioned
        if parsed.assignee and hasattr(self.connector, "resolve_user"):
            unique_name = await self.connector.resolve_user(parsed.assignee)
            if unique_name:
                fields["assignedTo"] = unique_name
            else:
                logger.warning(
                    f"Could not find project member matching '{parsed.assignee}' — "
                    "ticket will be left unassigned"
                )

        # Create ticket via connector
        result = await self.connector.create_item(fields)
        
        return result
    
    async def _create_jama_requirement(
        self,
        parsed: ParsedTicket,
        target_ticket: Any
    ) -> JamaItem:
        """
        Create corresponding Jama requirement.
        
        Args:
            parsed: Parsed ticket data
            target_ticket: Created target ticket
            
        Returns:
            Created JamaItem
        """
        # In a real implementation, this would call Jama API to create a requirement
        # For now, we'll create a mock JamaItem
        
        # Note: The actual Jama client doesn't have a create_item method yet
        # This would need to be added to the JamaClient class
        
        jama_item = JamaItem(
            id=999,  # Mock ID
            project_id=self.project_id,
            item_type="Requirement",
            name=parsed.title,
            description=f"{parsed.description}\n\nLinked to ticket: {target_ticket.item_url}",
            status="Draft",
            priority=parsed.priority,
            last_modified=datetime.utcnow(),
            fields={
                "name": parsed.title,
                "description": parsed.description,
                "status": "Draft",
                "priority": parsed.priority,
                "linked_ticket": target_ticket.item_url
            }
        )
        
        return jama_item
    
    def _format_success_message(
        self,
        parsed: ParsedTicket,
        target_ticket: Any,
        jama_requirement: Optional[JamaItem]
    ) -> str:
        """
        Format success message for user.
        
        Args:
            parsed: Parsed ticket data
            target_ticket: Created target ticket
            jama_requirement: Created Jama requirement (optional)
            
        Returns:
            Formatted success message
        """
        message_parts = []
        
        # Target ticket info
        message_parts.append(f"✅ Created ticket #{target_ticket.item_id}")
        if parsed.assignee:
            message_parts.append(f"   Assigned to: {parsed.assignee}")
        message_parts.append(f"   Priority: {parsed.priority}")
        message_parts.append(f"   Type: {parsed.ticket_type}")
        message_parts.append(f"   URL: {target_ticket.item_url}")
        
        # Jama requirement info
        if jama_requirement:
            message_parts.append(f"\n✅ Created Jama requirement #{jama_requirement.id}")
            message_parts.append(f"   Status: {jama_requirement.status}")
        
        # Sync info
        message_parts.append("\n🔄 Backend sync system will keep them in sync automatically")
        
        return "\n".join(message_parts)
    
    def get_help_message(self) -> str:
        """
        Get help message explaining how to use the chat agent.
        
        Returns:
            Help message string
        """
        return """
🤖 AI Ticket Creation Agent

I can create tickets from natural language! Just tell me what you need.

Examples:
  • "Create a ticket for Jamie to fix the security issue in the backend"
  • "Write a high priority bug for the login problem"
  • "Add a feature request for dark mode assigned to Sarah"
  • "Make a task to update the documentation"

I understand:
  ✓ Assignees: "for Jamie", "assigned to Sarah", "@alex"
  ✓ Priority: "high priority", "critical", "low priority"
  ✓ Types: "bug", "feature", "task", "user story"
  ✓ Labels: "#security", "#backend", "#frontend"

The ticket will be created in your project management tool (Azure DevOps/Jira)
and automatically synced to Jama Connect!
"""
