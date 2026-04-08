"""
Sync engine — tool-agnostic bidirectional orchestration.

Replaces the Jama-specific JamaClient references with source_connector /
target_connector (both BaseConnector), so any two connectors can be synced.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..config import AppConfig
from ..connectors.base import BaseConnector
from ..models.ticket import Activity, TargetItem, WebhookEvent
from ..models.mapping import SyncMapping
from ..models.action_log import ActionLog
from .mapper import FieldMapper

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Core orchestration logic for bidirectional synchronisation.

    Coordinates sync between a source connector and a target connector.
    Handles conflict detection, respects direction configuration, and
    writes an immutable audit log for every action.
    """

    def __init__(
        self,
        db_session: Session,
        source_connector: BaseConnector,
        target_connector: BaseConnector,
        mapper: FieldMapper,
        config: AppConfig,
    ):
        self.db = db_session
        self.source = source_connector
        self.target = target_connector
        self.mapper = mapper
        self.config = config
        # Human-readable names come from the sync config
        self._source_name = config.sync.source
        self._target_name = config.sync.target

    # ── Source → Target ───────────────────────────────────────────────────────

    async def process_source_update(self, activity: Activity) -> None:
        """
        Handle a change detected in the source connector.

        1. Fetches the full item from source.
        2. Finds or creates a mapping record.
        3. Creates / updates the item in the target connector.
        """
        if self.config.sync.direction == "target_to_source":
            logger.debug(
                "Skipping source update for item %s (direction is target_to_source)",
                activity.item_id,
            )
            return

        try:
            source_item = await self.source.get_item(str(activity.item_id))

            mapping = self.db.query(SyncMapping).filter_by(
                jama_item_id=activity.item_id,
                target_tool=self._target_name,
            ).first()

            if mapping is None:
                await self._create_target_item(source_item)
            else:
                await self._update_target_item(mapping, source_item)

        except Exception as e:
            logger.error("Failed to process source update for item %s: %s", activity.item_id, e, exc_info=True)
            await self._log_action(
                action="sync_error",
                source_tool=self._source_name,
                source_item_id=str(activity.item_id),
                target_tool=self._target_name,
                result="failed",
                payload={"activity": activity.to_dict(), "error": str(e)},
                error_detail=str(e),
            )

    async def _create_target_item(self, source_item: TargetItem) -> None:
        """Create a new item in the target connector and record the mapping."""
        try:
            target_fields = self.mapper.map_source_to_target(source_item)
            result = await self.target.create_item(target_fields)

            mapping = SyncMapping(
                jama_item_id=int(source_item.item_id) if source_item.item_id.isdigit() else 0,
                jama_project_id=0,
                jama_item_type="",
                target_tool=self._target_name,
                target_item_id=result.item_id,
                target_item_url=result.item_url,
                last_synced_at=datetime.utcnow(),
                sync_status="active",
            )
            self.db.add(mapping)
            self.db.commit()

            await self._log_action(
                action="create_ticket",
                source_tool=self._source_name,
                source_item_id=source_item.item_id,
                target_tool=self._target_name,
                target_item_id=result.item_id,
                result="success",
                payload={
                    "source_item": source_item.to_dict(),
                    "target_fields": target_fields,
                    "target_item_url": result.item_url,
                },
            )
            logger.info("Created target item %s for source item %s", result.item_id, source_item.item_id)

        except Exception as e:
            logger.error("Failed to create target item for source item %s: %s", source_item.item_id, e, exc_info=True)
            await self._log_action(
                action="create_ticket",
                source_tool=self._source_name,
                source_item_id=source_item.item_id,
                target_tool=self._target_name,
                result="failed",
                payload={"source_item": source_item.to_dict(), "error": str(e)},
                error_detail=str(e),
            )
            raise

    async def _update_target_item(self, mapping: SyncMapping, source_item: TargetItem) -> None:
        """Update the mapped target item if there is no conflict."""
        if mapping.sync_status in ("conflict", "error"):
            logger.warning(
                "Skipping update for source item %s — mapping is in '%s' state",
                source_item.item_id, mapping.sync_status,
            )
            return

        try:
            target_item = await self.target.get_item(mapping.target_item_id)

            if await self.detect_conflict(mapping, source_item, target_item):
                await self.handle_conflict(mapping, source_item, target_item)
                return

            target_fields = self.mapper.map_source_to_target(source_item)
            await self.target.update_item(mapping.target_item_id, target_fields)
            mapping.last_synced_at = datetime.utcnow()
            self.db.commit()

            await self._log_action(
                action="update_status",
                source_tool=self._source_name,
                source_item_id=source_item.item_id,
                target_tool=self._target_name,
                target_item_id=mapping.target_item_id,
                result="success",
                payload={"source_item": source_item.to_dict(), "target_fields": target_fields},
            )
            logger.info("Updated target item %s from source item %s", mapping.target_item_id, source_item.item_id)

        except Exception as e:
            logger.error("Failed to update target item for source item %s: %s", source_item.item_id, e, exc_info=True)
            mapping.sync_status = "error"
            self.db.commit()
            await self._log_action(
                action="update_status",
                source_tool=self._source_name,
                source_item_id=source_item.item_id,
                target_tool=self._target_name,
                target_item_id=mapping.target_item_id,
                result="failed",
                payload={"source_item": source_item.to_dict(), "error": str(e)},
                error_detail=str(e),
            )

    # ── Target → Source ───────────────────────────────────────────────────────

    async def process_target_update(self, event: WebhookEvent) -> None:
        """
        Handle an inbound webhook event from the target connector.

        1. Finds the mapping for the target item.
        2. Checks for conflicts.
        3. Pushes changes back to the source connector.
        """
        if self.config.sync.direction == "source_to_target":
            logger.debug(
                "Skipping target update for item %s (direction is source_to_target)",
                event.item_id,
            )
            return

        try:
            mapping = self.db.query(SyncMapping).filter_by(
                target_tool=self._target_name,
                target_item_id=event.item_id,
            ).first()

            if mapping is None:
                logger.warning("No mapping found for target item %s, skipping", event.item_id)
                return

            if mapping.sync_status in ("conflict", "error"):
                logger.warning(
                    "Skipping target update for item %s — mapping is in '%s' state",
                    event.item_id, mapping.sync_status,
                )
                return

            source_item = await self.source.get_item(str(mapping.jama_item_id))
            target_item = await self.target.get_item(event.item_id)

            if await self.detect_conflict(mapping, source_item, target_item):
                await self.handle_conflict(mapping, source_item, target_item)
                return

            source_fields = self.mapper.map_target_to_source(target_item)
            await self.source.update_item(str(mapping.jama_item_id), source_fields)
            mapping.last_synced_at = datetime.utcnow()
            self.db.commit()

            await self._log_action(
                action="update_status",
                source_tool=self._target_name,
                source_item_id=event.item_id,
                target_tool=self._source_name,
                target_item_id=str(mapping.jama_item_id),
                result="success",
                payload={
                    "webhook_event": event.to_dict(),
                    "target_item": target_item.to_dict(),
                    "source_fields": source_fields,
                },
            )
            logger.info("Updated source item %s from target item %s", mapping.jama_item_id, event.item_id)

        except Exception as e:
            logger.error("Failed to process target update for item %s: %s", event.item_id, e, exc_info=True)
            await self._log_action(
                action="sync_error",
                source_tool=self._target_name,
                source_item_id=event.item_id,
                target_tool=self._source_name,
                result="failed",
                payload={"webhook_event": event.to_dict(), "error": str(e)},
                error_detail=str(e),
            )

    # ── Conflict detection ────────────────────────────────────────────────────

    async def detect_conflict(
        self,
        mapping: SyncMapping,
        source_item: TargetItem,
        target_item: TargetItem,
    ) -> bool:
        """Return True if both sides were modified since the last sync."""
        source_modified = source_item.last_modified > mapping.last_synced_at
        target_modified = target_item.last_modified > mapping.last_synced_at
        conflict = source_modified and target_modified
        if conflict:
            logger.warning(
                "Conflict: source item %s (modified %s) and target item %s (modified %s) "
                "both changed since last sync at %s",
                source_item.item_id, source_item.last_modified,
                target_item.item_id, target_item.last_modified,
                mapping.last_synced_at,
            )
        return conflict

    async def handle_conflict(
        self,
        mapping: SyncMapping,
        source_item: TargetItem,
        target_item: TargetItem,
    ) -> None:
        """Flag the mapping as 'conflict' and log both states. Does not overwrite either side."""
        mapping.sync_status = "conflict"
        self.db.commit()
        await self._log_action(
            action="sync_error",
            source_tool="both",
            source_item_id=source_item.item_id,
            target_tool=self._target_name,
            target_item_id=target_item.item_id,
            result="conflict",
            payload={
                "source_state": source_item.to_dict(),
                "target_state": target_item.to_dict(),
                "last_synced_at": mapping.last_synced_at.isoformat(),
            },
            error_detail=(
                f"Both sides modified since last sync at {mapping.last_synced_at}. "
                f"Source modified at {source_item.last_modified}, "
                f"target modified at {target_item.last_modified}. "
                f"Manual resolution required."
            ),
        )
        logger.error(
            "Conflict flagged for source item %s / target item %s. Manual resolution required.",
            source_item.item_id, target_item.item_id,
        )

    # ── Audit log ─────────────────────────────────────────────────────────────

    async def log_action(self, **kwargs) -> None:
        """Public alias for backwards compatibility."""
        await self._log_action(**kwargs)

    async def _log_action(
        self,
        action: str,
        source_tool: str,
        result: str,
        payload: dict,
        source_item_id: Optional[str] = None,
        target_tool: Optional[str] = None,
        target_item_id: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """Write an immutable audit log entry to the database."""
        try:
            log_entry = ActionLog(
                timestamp=datetime.utcnow(),
                action=action,
                source_tool=source_tool,
                source_item_id=source_item_id,
                target_tool=target_tool,
                target_item_id=target_item_id,
                payload=json.dumps(payload, default=str),
                result=result,
                error_detail=error_detail,
            )
            self.db.add(log_entry)
            self.db.commit()
            logger.debug("Logged action '%s' from %s → result: %s", action, source_tool, result)
        except Exception as e:
            # Logging failure must not break sync
            logger.error("Failed to log action '%s': %s", action, e, exc_info=True)

    # ── Backwards-compat alias ────────────────────────────────────────────────

    async def process_jama_update(self, activity: Activity) -> None:
        """Deprecated — use process_source_update."""
        await self.process_source_update(activity)
