"""Sync engine core orchestration logic"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..config import AppConfig
from ..clients.jama_client import JamaClient
from ..clients.connectors.base import BaseConnector
from ..models.data_models import Activity, JamaItem, TargetItem, WebhookEvent
from ..models.mapping import SyncMapping
from ..models.action_log import ActionLog
from .mapper import FieldMapper


logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Core orchestration logic for bidirectional synchronization.
    
    Coordinates synchronization between Jama Connect and target tools,
    handles conflict detection, respects sync direction configuration,
    and maintains an immutable audit log.
    """
    
    def __init__(
        self,
        db_session: Session,
        jama_client: JamaClient,
        connector: BaseConnector,
        mapper: FieldMapper,
        config: AppConfig
    ):
        """
        Initialize sync engine.
        
        Args:
            db_session: SQLAlchemy database session
            jama_client: Jama Connect client
            connector: Target tool connector
            mapper: Field and status mapper
            config: Application configuration
        """
        self.db = db_session
        self.jama_client = jama_client
        self.connector = connector
        self.mapper = mapper
        self.config = config
    
    async def process_jama_update(self, activity: Activity) -> None:
        """
        Handle new or updated Jama item.
        
        This method:
        1. Checks if a mapping exists for the Jama item
        2. For new items: creates target tool item, stores mapping, logs action
        3. For existing items: checks for conflicts, updates target if safe
        4. Respects sync direction configuration
        
        Args:
            activity: Jama activity event
        """
        # Check sync direction - skip if target_to_jama only
        if self.config.sync.direction == "target_to_jama":
            logger.debug(
                f"Skipping Jama update for item {activity.item_id} "
                f"(sync direction is target_to_jama)"
            )
            return
        
        try:
            # Get full item details from Jama
            jama_item = await self.jama_client.get_item(activity.item_id)
            
            # Check if mapping exists
            mapping = self.db.query(SyncMapping).filter_by(
                jama_item_id=activity.item_id,
                target_tool=self.config.target_tool.tool_type
            ).first()
            
            if mapping is None:
                # New item - create in target tool
                await self._create_target_item(jama_item)
            else:
                # Existing mapping - check for conflicts and update
                await self._update_target_item(mapping, jama_item)
                
        except Exception as e:
            logger.error(
                f"Failed to process Jama update for item {activity.item_id}: {e}",
                exc_info=True
            )
            # Log error action
            await self.log_action(
                action="sync_error",
                source_tool="jama",
                source_item_id=str(activity.item_id),
                target_tool=self.config.target_tool.tool_type,
                result="failed",
                payload={"activity": activity.to_dict(), "error": str(e)},
                error_detail=str(e)
            )
    
    async def _create_target_item(self, jama_item: JamaItem) -> None:
        """
        Create new item in target tool and store mapping.
        
        Args:
            jama_item: Jama item to create in target tool
        """
        try:
            # Map Jama fields to target tool format
            target_fields = self.mapper.map_jama_to_target(jama_item)
            
            # Create item in target tool
            result = await self.connector.create_item(target_fields)
            
            # Store mapping
            mapping = SyncMapping(
                jama_item_id=jama_item.id,
                jama_project_id=jama_item.project_id,
                jama_item_type=jama_item.item_type,
                target_tool=self.config.target_tool.tool_type,
                target_item_id=result.item_id,
                target_item_url=result.item_url,
                last_synced_at=datetime.utcnow(),
                sync_status="active"
            )
            self.db.add(mapping)
            self.db.commit()
            
            # Log successful creation
            await self.log_action(
                action="create_ticket",
                source_tool="jama",
                source_item_id=str(jama_item.id),
                target_tool=self.config.target_tool.tool_type,
                target_item_id=result.item_id,
                result="success",
                payload={
                    "jama_item": jama_item.to_dict(),
                    "target_fields": target_fields,
                    "target_item_id": result.item_id,
                    "target_item_url": result.item_url
                }
            )
            
            logger.info(
                f"Created target item {result.item_id} for Jama item {jama_item.id}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to create target item for Jama item {jama_item.id}: {e}",
                exc_info=True
            )
            # Log error
            await self.log_action(
                action="create_ticket",
                source_tool="jama",
                source_item_id=str(jama_item.id),
                target_tool=self.config.target_tool.tool_type,
                result="failed",
                payload={"jama_item": jama_item.to_dict(), "error": str(e)},
                error_detail=str(e)
            )
            raise
    
    async def _update_target_item(
        self,
        mapping: SyncMapping,
        jama_item: JamaItem
    ) -> None:
        """
        Update existing target item, checking for conflicts first.
        
        Args:
            mapping: Existing sync mapping
            jama_item: Updated Jama item
        """
        # Skip if mapping is in conflict or error state
        if mapping.sync_status == "conflict":
            logger.warning(
                f"Skipping update for Jama item {jama_item.id} - "
                f"mapping is in conflict state"
            )
            return
        
        if mapping.sync_status == "error":
            logger.warning(
                f"Skipping update for Jama item {jama_item.id} - "
                f"mapping is in error state"
            )
            return
        
        try:
            # Get current target item state
            target_item = await self.connector.get_item(mapping.target_item_id)
            
            # Check for conflicts
            if await self.detect_conflict(mapping, jama_item, target_item):
                await self.handle_conflict(mapping, jama_item, target_item)
                return
            
            # No conflict - safe to update
            target_fields = self.mapper.map_jama_to_target(jama_item)
            await self.connector.update_item(mapping.target_item_id, target_fields)
            
            # Update mapping timestamp
            mapping.last_synced_at = datetime.utcnow()
            self.db.commit()
            
            # Log successful update
            await self.log_action(
                action="update_status",
                source_tool="jama",
                source_item_id=str(jama_item.id),
                target_tool=self.config.target_tool.tool_type,
                target_item_id=mapping.target_item_id,
                result="success",
                payload={
                    "jama_item": jama_item.to_dict(),
                    "target_fields": target_fields
                }
            )
            
            logger.info(
                f"Updated target item {mapping.target_item_id} "
                f"from Jama item {jama_item.id}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to update target item for Jama item {jama_item.id}: {e}",
                exc_info=True
            )
            # Mark mapping as error
            mapping.sync_status = "error"
            self.db.commit()
            
            # Log error
            await self.log_action(
                action="update_status",
                source_tool="jama",
                source_item_id=str(jama_item.id),
                target_tool=self.config.target_tool.tool_type,
                target_item_id=mapping.target_item_id,
                result="failed",
                payload={"jama_item": jama_item.to_dict(), "error": str(e)},
                error_detail=str(e)
            )
    
    async def process_target_update(self, event: WebhookEvent) -> None:
        """
        Handle target tool webhook event.
        
        This method:
        1. Looks up the mapping for the target item
        2. Checks for conflicts
        3. Updates Jama item if safe
        4. Respects sync direction configuration
        
        Args:
            event: Webhook event from target tool
        """
        # Check sync direction - skip if jama_to_target only
        if self.config.sync.direction == "jama_to_target":
            logger.debug(
                f"Skipping target update for item {event.item_id} "
                f"(sync direction is jama_to_target)"
            )
            return
        
        try:
            # Look up mapping
            mapping = self.db.query(SyncMapping).filter_by(
                target_tool=self.config.target_tool.tool_type,
                target_item_id=event.item_id
            ).first()
            
            if mapping is None:
                logger.warning(
                    f"No mapping found for target item {event.item_id}, skipping"
                )
                return
            
            # Skip if mapping is in conflict or error state
            if mapping.sync_status == "conflict":
                logger.warning(
                    f"Skipping update for target item {event.item_id} - "
                    f"mapping is in conflict state"
                )
                return
            
            if mapping.sync_status == "error":
                logger.warning(
                    f"Skipping update for target item {event.item_id} - "
                    f"mapping is in error state"
                )
                return
            
            # Get current states
            jama_item = await self.jama_client.get_item(mapping.jama_item_id)
            target_item = await self.connector.get_item(event.item_id)
            
            # Check for conflicts
            if await self.detect_conflict(mapping, jama_item, target_item):
                await self.handle_conflict(mapping, jama_item, target_item)
                return
            
            # No conflict - safe to update Jama
            jama_fields = self.mapper.map_target_to_jama(target_item)
            await self.jama_client.update_item(mapping.jama_item_id, jama_fields)
            
            # Update mapping timestamp
            mapping.last_synced_at = datetime.utcnow()
            self.db.commit()
            
            # Log successful update
            await self.log_action(
                action="update_status",
                source_tool=self.config.target_tool.tool_type,
                source_item_id=event.item_id,
                target_tool="jama",
                target_item_id=str(mapping.jama_item_id),
                result="success",
                payload={
                    "webhook_event": event.to_dict(),
                    "target_item": target_item.to_dict(),
                    "jama_fields": jama_fields
                }
            )
            
            logger.info(
                f"Updated Jama item {mapping.jama_item_id} "
                f"from target item {event.item_id}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to process target update for item {event.item_id}: {e}",
                exc_info=True
            )
            # Log error
            await self.log_action(
                action="sync_error",
                source_tool=self.config.target_tool.tool_type,
                source_item_id=event.item_id,
                target_tool="jama",
                result="failed",
                payload={"webhook_event": event.to_dict(), "error": str(e)},
                error_detail=str(e)
            )
    
    async def detect_conflict(
        self,
        mapping: SyncMapping,
        jama_item: JamaItem,
        target_item: TargetItem
    ) -> bool:
        """
        Detect if both sides modified since last sync.
        
        A conflict occurs when both Jama and the target tool have been
        modified since the last successful sync.
        
        Args:
            mapping: Sync mapping with last_synced_at timestamp
            jama_item: Current Jama item state
            target_item: Current target item state
            
        Returns:
            True if conflict detected, False otherwise
        """
        jama_modified = jama_item.last_modified > mapping.last_synced_at
        target_modified = target_item.last_modified > mapping.last_synced_at
        
        conflict = jama_modified and target_modified
        
        if conflict:
            logger.warning(
                f"Conflict detected for Jama item {jama_item.id} / "
                f"target item {target_item.item_id}: "
                f"Jama modified at {jama_item.last_modified}, "
                f"target modified at {target_item.last_modified}, "
                f"last synced at {mapping.last_synced_at}"
            )
        
        return conflict
    
    async def handle_conflict(
        self,
        mapping: SyncMapping,
        jama_item: JamaItem,
        target_item: TargetItem
    ) -> None:
        """
        Flag conflict and log details without overwriting.
        
        When a conflict is detected, this method:
        1. Sets mapping sync_status to "conflict"
        2. Logs the conflict with both states in the payload
        3. Does NOT overwrite either side
        
        Args:
            mapping: Sync mapping to flag as conflict
            jama_item: Current Jama item state
            target_item: Current target item state
        """
        # Flag mapping as conflict
        mapping.sync_status = "conflict"
        self.db.commit()
        
        # Log conflict with both states
        await self.log_action(
            action="sync_error",
            source_tool="both",
            source_item_id=str(jama_item.id),
            target_tool=self.config.target_tool.tool_type,
            target_item_id=target_item.item_id,
            result="conflict",
            payload={
                "jama_state": jama_item.to_dict(),
                "target_state": target_item.to_dict(),
                "last_synced_at": mapping.last_synced_at.isoformat()
            },
            error_detail=(
                f"Both systems modified since last sync at {mapping.last_synced_at}. "
                f"Jama modified at {jama_item.last_modified}, "
                f"target modified at {target_item.last_modified}. "
                f"Manual resolution required."
            )
        )
        
        logger.error(
            f"Conflict flagged for Jama item {jama_item.id} / "
            f"target item {target_item.item_id}. Manual resolution required."
        )
    
    async def log_action(
        self,
        action: str,
        source_tool: str,
        result: str,
        payload: dict,
        source_item_id: Optional[str] = None,
        target_tool: Optional[str] = None,
        target_item_id: Optional[str] = None,
        error_detail: Optional[str] = None
    ) -> None:
        """
        Create immutable audit log entry.
        
        All sync actions are logged to the ActionLog table for regulatory
        compliance. Entries are immutable and include full payload data.
        
        Args:
            action: Action type (create_ticket, update_status, link_items, sync_error)
            source_tool: Source system name
            result: Result status (success, failed, conflict)
            payload: Full payload with before/after states
            source_item_id: Source item ID (optional)
            target_tool: Target system name (optional)
            target_item_id: Target item ID (optional)
            error_detail: Error details if result is failed or conflict (optional)
        """
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
                error_detail=error_detail
            )
            
            self.db.add(log_entry)
            self.db.commit()
            
            logger.debug(
                f"Logged action: {action} from {source_tool} "
                f"with result {result}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to log action {action}: {e}",
                exc_info=True
            )
            # Don't raise - logging failure shouldn't break sync
