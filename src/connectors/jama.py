"""
Jama Connect connector — thin wrapper around the existing JamaClient.

JamaClient handles rate limiting, exponential backoff, and the synchronous
py-jama-rest-client calls. This class adapts it to the BaseConnector interface
so Jama can act as a source (or target) in the generic sync engine.

Note: Jama is typically the *source* of truth, not the target, so
create_item / update_item delegate to JamaClient.update_item where possible.
Full item creation via the REST API requires an itemType ID which is
project-specific; the implementation uses the JamaClient for this.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseConnector
from ..models.ticket import Activity, CreateItemResult, TargetItem, WebhookEvent
from ..clients.jama_client import JamaClient
from ..config import JamaConfig

logger = logging.getLogger(__name__)


class JamaConnector(BaseConnector):
    """
    Jama Connect connector.

    Wraps JamaClient (which in turn wraps py-jama-rest-client) and exposes
    the standard BaseConnector interface. Jama does not support webhooks in the
    same push model as Jira/ADO, so parse_webhook raises NotImplementedError.
    """

    # Canonical → Jama priority string (project-dependent; adjust as needed)
    _PRIORITY_MAP: Dict[str, str] = {
        "critical": "Critical",
        "high":     "High",
        "medium":   "Medium",
        "low":      "Low",
    }

    # Canonical ticket type → Jama item type name
    _TYPE_MAP: Dict[str, str] = {
        "bug":        "Defect",
        "feature":    "Feature",
        "task":       "Task",
        "user story": "User Story",
    }

    def __init__(self, base_url: str, username: str, password: str, project_id: int):
        config = JamaConfig(
            base_url=base_url,
            username=username,
            password=password,
            project_id=project_id,
        )
        self._client = JamaClient(config)
        self.project_id = project_id

    # ── Field normalisation ───────────────────────────────────────────────────

    def normalize_priority(self, canonical: str) -> str:
        """
        Convert canonical priority → Jama priority string.

        Args:
            canonical: "critical" | "high" | "medium" | "low"

        Returns:
            Jama priority string. Defaults to "Medium".
        """
        return self._PRIORITY_MAP.get(canonical.lower(), "Medium")

    def normalize_type(self, canonical: str) -> str:
        """
        Convert canonical ticket type → Jama item type name.

        Args:
            canonical: "Bug" | "Feature" | "Task" | "User Story"

        Returns:
            Jama item type string. Defaults to "Task".
        """
        return self._TYPE_MAP.get(canonical.lower(), "Task")

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """
        Create a Jama item.

        Note: py-jama-rest-client requires an itemType ID (numeric), which is
        project-specific. The caller should pass `item_type_id` in fields, or
        we fall back to the first available type in the project (not implemented
        here — extend as needed for your Jama instance).
        """
        raise NotImplementedError(
            "JamaConnector.create_item is not yet implemented. "
            "Jama is typically used as a sync source, not a creation target. "
            "To create Jama items, extend this method with your project's itemType IDs."
        )

    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """
        Update a Jama item's fields.

        Args:
            item_id: Jama item ID (numeric, passed as string).
            fields:  Dict of field names → values to update.
        """
        await self._client.update_item(int(item_id), fields)

    async def get_item(self, item_id: str) -> TargetItem:
        """
        Retrieve a Jama item and normalise it to TargetItem.

        Args:
            item_id: Jama item ID (numeric, passed as string).
        """
        jama_item = await self._client.get_item(int(item_id))
        return TargetItem(
            item_id=str(jama_item.id),
            title=jama_item.name,
            description=jama_item.description,
            status=jama_item.status,
            priority=jama_item.priority,
            last_modified=jama_item.last_modified,
            fields=jama_item.fields,
        )

    # ── Webhooks ──────────────────────────────────────────────────────────────

    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Jama does not push webhooks in a standard format.

        If your Jama instance has webhook support configured, implement parsing
        here. Until then this raises NotImplementedError to make the gap visible.
        """
        raise NotImplementedError(
            "JamaConnector.parse_webhook is not implemented. "
            "Jama sync is driven by activity polling (get_activities), not webhooks."
        )

    # ── Connectivity ──────────────────────────────────────────────────────────

    async def validate_connection(self) -> bool:
        """Verify connectivity by fetching a single activity (lightweight call)."""
        try:
            await self._client.get_activities(since=datetime.utcnow())
            logger.info("Jama connection validated for project %s", self.project_id)
            return True
        except Exception as e:
            logger.error("Jama connection validation failed: %s", e)
            return False

    # ── Activity stream (source connector) ───────────────────────────────────

    async def get_activities(self, since: datetime) -> List[Activity]:
        """
        Poll the Jama activity stream for changes since *since*.

        Used by ConnectorPoller to detect changes and trigger sync.
        """
        return await self._client.get_activities(since=since)
