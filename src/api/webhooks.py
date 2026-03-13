"""Webhook endpoints for receiving events from target tools"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..sync.engine import SyncEngine
from ..clients.connectors.base import BaseConnector


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# Dependency injection placeholders - will be set by main.py
_sync_engine: SyncEngine | None = None
_connector: BaseConnector | None = None


def set_dependencies(sync_engine: SyncEngine, connector: BaseConnector):
    """Set dependencies for webhook endpoints"""
    global _sync_engine, _connector
    _sync_engine = sync_engine
    _connector = connector


def get_sync_engine() -> SyncEngine:
    """Dependency to get sync engine"""
    if _sync_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sync engine not initialized"
        )
    return _sync_engine


def get_connector() -> BaseConnector:
    """Dependency to get connector"""
    if _connector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connector not initialized"
        )
    return _connector


@router.post("/{tool_name}")
async def receive_webhook(
    tool_name: str,
    payload: Dict[str, Any],
    sync_engine: SyncEngine = Depends(get_sync_engine),
    connector: BaseConnector = Depends(get_connector)
):
    """
    Receive and process webhook from target tool.
    
    This endpoint receives webhook events from target tools (Azure DevOps, GitLab, Jira)
    when work items are created or updated. The webhook payload is parsed and processed
    to update the corresponding Jama item.
    
    Args:
        tool_name: Name of the target tool sending the webhook
        payload: Webhook payload from target tool
        sync_engine: Sync engine dependency
        connector: Connector dependency
        
    Returns:
        Status message indicating webhook was processed
        
    Raises:
        HTTPException: If webhook processing fails
    """
    try:
        logger.info(f"Received webhook from {tool_name}")
        logger.debug(f"Webhook payload: {payload}")
        
        # Parse webhook payload using connector
        event = connector.parse_webhook(payload)
        
        # Process the event through sync engine
        await sync_engine.process_target_update(event)
        
        logger.info(
            f"Successfully processed webhook for item {event.item_id} "
            f"from {tool_name}"
        )
        
        return {
            "status": "processed",
            "tool": tool_name,
            "item_id": event.item_id,
            "event_type": event.event_type
        }
        
    except ValueError as e:
        # Invalid webhook payload - return 400
        logger.warning(
            f"Invalid webhook payload from {tool_name}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {str(e)}"
        )
    except Exception as e:
        # Other errors - log with full context and return 500
        logger.error(
            f"Failed to process webhook from {tool_name}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


@router.post("/sync/trigger")
async def trigger_sync(
    sync_engine: SyncEngine = Depends(get_sync_engine),
    db: Session = Depends(get_session)
):
    """
    Manually trigger a sync cycle.
    
    This endpoint allows administrators to manually trigger a Jama poll
    and sync cycle without waiting for the scheduled interval.
    
    Args:
        sync_engine: Sync engine dependency
        db: Database session dependency
        
    Returns:
        Status message with sync results
        
    Raises:
        HTTPException: If sync trigger fails
    """
    try:
        logger.info("Manual sync trigger requested")
        
        # Import here to avoid circular dependency
        from ..sync.poller import JamaPoller
        from ..clients.jama_client import JamaClient
        from ..config import load_config
        
        # Get poller instance (this is a simplified version)
        # In production, this should use the same poller instance as the scheduler
        config = load_config()
        jama_client = JamaClient(config.jama)
        poller = JamaPoller(jama_client, sync_engine)
        
        # Trigger poll
        result = await poller.poll()
        
        if result.success:
            logger.info(
                f"Manual sync completed: processed {result.items_processed} items"
            )
            return {
                "status": "success",
                "items_processed": result.items_processed,
                "message": "Sync cycle completed successfully"
            }
        else:
            logger.error(f"Manual sync failed: {result.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sync failed: {result.error}"
            )
            
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger sync: {str(e)}"
        )
