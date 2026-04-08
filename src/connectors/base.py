"""
Tool-agnostic BaseConnector interface.

Every connector (Azure DevOps, Jira, Jama, …) must implement the abstract
methods. The non-abstract methods have safe defaults so connectors can opt in
to features incrementally instead of implementing everything at once.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.ticket import Activity, CreateItemResult, TargetItem, WebhookEvent


class BaseConnector(ABC):
    """
    Abstract base class for all tool connectors.

    Concrete connectors must implement:
      - create_item / update_item / get_item   — CRUD
      - parse_webhook                          — inbound webhook normalisation
      - validate_connection                    — health check
      - normalize_priority                     — canonical → tool-native priority
      - normalize_type                         — canonical → tool-native type string

    Optional overrides (default: safe no-ops):
      - get_activities   — activity stream for polling
      - list_items       — recent items listing (for UI / MCP)
      - list_members     — team member roster (for @mention autocomplete)
      - resolve_user     — name → native user ID / email
      - close            — clean up HTTP client
    """

    # ── Required: CRUD ────────────────────────────────────────────────────────

    @abstractmethod
    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """
        Create a new work item.

        Args:
            fields: Tool-agnostic field dict (title, description, priority, type, …).

        Returns:
            CreateItemResult with item_id, item_url, created_at.
        """

    @abstractmethod
    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """
        Update an existing work item.

        Args:
            item_id: Native item ID.
            fields:  Fields to update.
        """

    @abstractmethod
    async def get_item(self, item_id: str) -> TargetItem:
        """
        Retrieve a work item's current state.

        Args:
            item_id: Native item ID.

        Returns:
            TargetItem snapshot.
        """

    # ── Required: webhooks ────────────────────────────────────────────────────

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Parse a raw inbound webhook payload into a standardised WebhookEvent.

        Args:
            payload: Raw JSON body from the tool.

        Returns:
            WebhookEvent with event_type, item_id, updated_fields, timestamp.
        """

    # ── Required: connectivity ────────────────────────────────────────────────

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Verify that credentials and base_url are valid.

        Returns:
            True if the API responds successfully, False otherwise.
        """

    # ── Required: field normalisation ─────────────────────────────────────────

    @abstractmethod
    def normalize_priority(self, canonical: str) -> Any:
        """
        Convert a canonical priority string to this tool's native format.

        Canonical values: "critical" | "high" | "medium" | "low"

        Examples:
          Azure DevOps → int  (1 = Critical, 2 = High, 3 = Medium, 4 = Low)
          Jira         → dict ({"name": "High"})
          Jama         → str  ("High")

        Args:
            canonical: Lowercase canonical priority string.

        Returns:
            Tool-native priority value (type varies by connector).
        """

    @abstractmethod
    def normalize_type(self, canonical: str) -> str:
        """
        Convert a canonical ticket type to this tool's native type name.

        Canonical values: "Bug" | "Feature" | "Task" | "User Story"

        Examples:
          Azure DevOps → "Bug" / "Epic" / "Task" / "User Story"
          Jira         → "Bug" / "Story" / "Task" / "Story"
          Jama         → item type string (tool-specific)

        Args:
            canonical: Canonical type string (title-cased).

        Returns:
            Tool-native type name string.
        """

    # ── Optional: activity polling ────────────────────────────────────────────

    async def get_activities(self, since: datetime) -> List[Activity]:
        """
        Return activity events since *since*.

        Used by ConnectorPoller to drive bidirectional sync.  Connectors that
        don't support an activity stream can leave this as-is — the poller
        will simply see no events and skip the sync cycle.

        Args:
            since: Only return activities after this timestamp.

        Returns:
            List of Activity objects (empty list if unsupported).
        """
        return []

    # ── Optional: listing ─────────────────────────────────────────────────────

    async def list_items(self, limit: int = 10) -> List[dict]:
        """
        Return the most recently modified items as plain dicts.

        Used by the MCP server's list_recent_tickets tool and the web UI.
        Keys are connector-specific but should include at minimum:
          id, title, state/status, url

        Args:
            limit: Maximum number of items (connectors may cap lower).

        Returns:
            List of dicts (empty list if unsupported).
        """
        return []

    async def list_members(self) -> List[dict]:
        """
        Return project team members for @mention autocomplete.

        Each dict should include at minimum:
          displayName, uniqueName (or accountId / email)

        Returns:
            List of dicts (empty list if unsupported).
        """
        return []

    # ── Optional: user resolution ─────────────────────────────────────────────

    async def resolve_user(self, name: str) -> Optional[str]:
        """
        Look up a user by display name and return their native ID / email.

        Used by ChatAgent to wire up assignee_id without tool-specific logic.

        Args:
            name: Display name or partial name to search for.

        Returns:
            Native user identifier, or None if not found / unsupported.
        """
        return None

    # ── Optional: cleanup ─────────────────────────────────────────────────────

    async def close(self) -> None:
        """
        Release resources (HTTP clients, DB connections, etc.).

        Called during app shutdown. Safe to leave as no-op.
        """
