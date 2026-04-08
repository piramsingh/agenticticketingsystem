"""
Chat agent — natural language → ticket creation.

Tool-specific priority/type mapping is now delegated to the connector via
normalize_priority() and normalize_type(), so this class stays tool-agnostic.
"""
import logging
from typing import Any, Dict, Optional

from .ticket_parser import TicketParser, ParsedTicket
from ..connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class ChatAgent:
    """
    AI-powered chat agent for creating tickets from natural language.

    Steps:
    1. Parse user input → ParsedTicket (via TicketParser / Claude)
    2. Ask the connector to normalise priority and type to its native format
    3. Optionally resolve the assignee name to a native user ID
    4. Call connector.create_item(fields)
    """

    def __init__(self, parser: TicketParser, connector: BaseConnector):
        self.parser = parser
        self.connector = connector

    async def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Parse *user_input* and create a ticket in the connected tool.

        Args:
            user_input: Free-form natural language description.

        Returns:
            Dict with keys: success, parsed, target_ticket, message  (or error).
        """
        try:
            logger.info("Processing message: %s", user_input)
            parsed = self.parser.parse(user_input)
            logger.info("Parsed ticket: %s", parsed)

            result = await self._create_target_ticket(parsed)
            logger.info("Created ticket: %s", result.item_id)

            return {
                "success": True,
                "parsed": parsed.to_dict(),
                "target_ticket": {
                    "id":         result.item_id,
                    "url":        result.item_url,
                    "created_at": result.created_at.isoformat(),
                },
                "message": self._format_success_message(parsed, result),
            }

        except Exception as e:
            logger.error("Failed to process message: %s", e, exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create ticket: {e}",
            }

    async def _create_target_ticket(self, parsed: ParsedTicket) -> Any:
        """
        Build the field dict and call connector.create_item().

        Priority and type are normalised by the connector — no tool-specific
        maps live in this class.
        """
        canonical_priority = (parsed.priority or "medium").lower()
        canonical_type     = parsed.ticket_type or "Task"

        fields: Dict[str, Any] = {
            "title":       parsed.title,
            "description": parsed.description or "",
            "priority":    self.connector.normalize_priority(canonical_priority),
            "type":        self.connector.normalize_type(canonical_type),
        }

        if parsed.labels:
            fields["tags"] = ", ".join(parsed.labels)

        # resolve_user is on BaseConnector with a safe None default — no hasattr needed
        if parsed.assignee:
            user_id = await self.connector.resolve_user(parsed.assignee)
            if user_id:
                fields["assignee_id"] = user_id
            else:
                logger.warning(
                    "Could not resolve user '%s' — ticket will be left unassigned",
                    parsed.assignee,
                )

        return await self.connector.create_item(fields)

    def _format_success_message(self, parsed: ParsedTicket, ticket: Any) -> str:
        parts = [f"Created ticket #{ticket.item_id}"]
        if parsed.assignee:
            parts.append(f"  Assigned to: {parsed.assignee}")
        parts.append(f"  Priority: {parsed.priority}")
        parts.append(f"  Type: {parsed.ticket_type}")
        parts.append(f"  URL: {ticket.item_url}")
        return "\n".join(parts)

    def get_help_message(self) -> str:
        return (
            "AI Ticket Creation Agent\n\n"
            "Tell me what you need and I'll create a ticket.\n\n"
            "Examples:\n"
            '  "Create a ticket for Jamie to fix the security issue in the backend"\n'
            '  "High priority bug: login fails on Safari"\n'
            '  "Feature request for dark mode, assign to Sarah"\n\n'
            "I understand: assignees, priority, type (bug/feature/task/user story), labels (#tag)."
        )
