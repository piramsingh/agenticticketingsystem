"""Health check endpoint for monitoring system status"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_session
from ..models.mapping import SyncMapping
from ..models.action_log import ActionLog


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


# Global reference to poller for last_poll_time
_poller = None


def set_poller(poller):
    """Set poller reference for health checks"""
    global _poller
    _poller = poller


@router.get("")
async def health_check(db: Session = Depends(get_session)):
    """
    Return system health status.
    
    This endpoint provides monitoring information including:
    - Overall system status
    - Last successful poll time
    - Count of mappings in conflict state
    - Count of mappings in error state
    - Recent error count from action logs
    
    Args:
        db: Database session dependency
        
    Returns:
        Health status dictionary with monitoring metrics
    """
    try:
        # Count mappings by status
        conflict_count = db.query(func.count(SyncMapping.id)).filter(
            SyncMapping.sync_status == "conflict"
        ).scalar() or 0
        
        error_count = db.query(func.count(SyncMapping.id)).filter(
            SyncMapping.sync_status == "error"
        ).scalar() or 0
        
        active_count = db.query(func.count(SyncMapping.id)).filter(
            SyncMapping.sync_status == "active"
        ).scalar() or 0
        
        # Count recent errors in action log (last 24 hours)
        recent_errors = db.query(func.count(ActionLog.id)).filter(
            ActionLog.result.in_(["failed", "conflict"]),
            ActionLog.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).scalar() or 0
        
        # Get last poll time from poller
        last_poll: Optional[datetime] = None
        if _poller is not None:
            last_poll = _poller.last_poll_time
        
        # Determine overall status
        if conflict_count > 0 or error_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        response = {
            "status": overall_status,
            "last_poll": last_poll.isoformat() if last_poll else None,
            "mappings": {
                "active": active_count,
                "conflicts": conflict_count,
                "errors": error_count,
                "total": active_count + conflict_count + error_count
            },
            "recent_errors": recent_errors,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Health check: {response}")
        
        return response
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
