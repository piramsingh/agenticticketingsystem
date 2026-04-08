"""
ConnectorPoller — polls the source connector's activity stream.

Replaces the Jama-specific JamaPoller. Any connector that implements
get_activities() can be used as a source.

JamaPoller is kept as a backwards-compat alias.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..connectors.base import BaseConnector
from ..models.ticket import PollResult
from .engine import SyncEngine

logger = logging.getLogger(__name__)


class ConnectorPoller:
    """
    Polls a source connector's activity stream on a schedule.

    On each cycle:
    1. Calls source.get_activities(since=last_poll_time)
    2. Filters for ITEM_CREATED / ITEM_UPDATED events
    3. Forwards each activity to SyncEngine.process_source_update
    4. Updates last_poll_time on success

    Connectors that don't implement get_activities() return an empty list,
    making the poll a no-op (used for single-connector / Jira-only configs).
    """

    def __init__(self, source_connector: BaseConnector, sync_engine: SyncEngine):
        self.source = source_connector
        self.sync_engine = sync_engine
        self.last_poll_time: Optional[datetime] = None

    async def poll(self) -> PollResult:
        """
        Run one poll cycle.

        Returns:
            PollResult with success flag, items_processed count, and optional error.
        """
        try:
            # On first poll, look back 1 hour to catch recent changes
            since = self.last_poll_time or (datetime.utcnow() - timedelta(hours=1))
            logger.info("Polling source connector activities since %s", since)

            activities = await self.source.get_activities(since=since)

            relevant = [
                a for a in activities
                if a.activity_type in ("ITEM_CREATED", "ITEM_UPDATED")
            ]
            logger.info(
                "Found %d relevant activities out of %d total",
                len(relevant), len(activities),
            )

            processed = 0
            for activity in relevant:
                try:
                    await self.sync_engine.process_source_update(activity)
                    processed += 1
                except Exception as e:
                    logger.error(
                        "Failed to process activity %s for item %s: %s",
                        activity.id, activity.item_id, e, exc_info=True,
                    )

            self.last_poll_time = datetime.utcnow()
            logger.info("Poll complete: processed %d / %d relevant activities", processed, len(relevant))
            return PollResult(success=True, items_processed=processed)

        except Exception as e:
            logger.error("Poll failed: %s", e, exc_info=True)
            # Don't update last_poll_time so next cycle retries from same window
            return PollResult(success=False, items_processed=0, error=str(e))


# Backwards-compat alias — old code that imports JamaPoller keeps working
JamaPoller = ConnectorPoller
