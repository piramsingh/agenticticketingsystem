"""Jama activity polling subsystem"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..clients.jama_client import JamaClient
from ..models.data_models import PollResult
from .engine import SyncEngine


logger = logging.getLogger(__name__)


class JamaPoller:
    """
    Polls Jama Connect activity stream for changes.
    
    This poller runs on a schedule (default 60 seconds) and queries Jama's
    activity stream for ITEM_CREATED and ITEM_UPDATED events. It filters
    activities for the configured project and passes relevant events to the
    sync engine for processing.
    
    Attributes:
        jama_client: Jama Connect client for API calls
        sync_engine: Sync engine for processing updates
        last_poll_time: Timestamp of last successful poll
    """
    
    def __init__(self, jama_client: JamaClient, sync_engine: SyncEngine):
        """
        Initialize Jama poller.
        
        Args:
            jama_client: Jama Connect client
            sync_engine: Sync engine for processing updates
        """
        self.jama_client = jama_client
        self.sync_engine = sync_engine
        self.last_poll_time: Optional[datetime] = None
    
    async def poll(self) -> PollResult:
        """
        Poll Jama activities and trigger sync for new/updated items.
        
        This method:
        1. Queries Jama activities API since last poll time
        2. Filters for ITEM_CREATED and ITEM_UPDATED events
        3. Passes relevant activities to sync engine
        4. Updates last_poll_time on success
        5. Handles errors gracefully to continue on next cycle
        
        Returns:
            PollResult with success status, items processed count, and error if any
        """
        try:
            # Determine poll start time
            # On first poll, look back 1 hour to catch recent changes
            since = self.last_poll_time or (datetime.utcnow() - timedelta(hours=1))
            
            logger.info(f"Polling Jama activities since {since}")
            
            # Get activities from Jama
            activities = await self.jama_client.get_activities(since=since)
            
            # Filter for relevant activity types
            relevant_activities = [
                activity for activity in activities
                if activity.activity_type in ['ITEM_CREATED', 'ITEM_UPDATED']
            ]
            
            logger.info(
                f"Found {len(relevant_activities)} relevant activities "
                f"out of {len(activities)} total"
            )
            
            # Process each relevant activity
            processed_count = 0
            for activity in relevant_activities:
                try:
                    await self.sync_engine.process_jama_update(activity)
                    processed_count += 1
                except Exception as e:
                    # Log error but continue processing other activities
                    logger.error(
                        f"Failed to process activity {activity.id} "
                        f"for item {activity.item_id}: {e}",
                        exc_info=True
                    )
            
            # Update last poll time on success
            self.last_poll_time = datetime.utcnow()
            
            logger.info(
                f"Poll completed successfully: processed {processed_count} "
                f"out of {len(relevant_activities)} relevant activities"
            )
            
            return PollResult(
                success=True,
                items_processed=processed_count
            )
            
        except Exception as e:
            # Log error and return failure result
            # Don't update last_poll_time so we retry from same point
            logger.error(
                f"Poll failed: {e}",
                exc_info=True
            )
            
            return PollResult(
                success=False,
                items_processed=0,
                error=str(e)
            )
