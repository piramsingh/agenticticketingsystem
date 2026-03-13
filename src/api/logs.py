"""Action log query endpoints for audit trail access"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models.action_log import ActionLog


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def query_logs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    start_date: Optional[datetime] = Query(None, description="Filter logs after this date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter logs before this date (ISO 8601)"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    result: Optional[str] = Query(None, description="Filter by result (success, failed, conflict)"),
    source_tool: Optional[str] = Query(None, description="Filter by source tool"),
    target_tool: Optional[str] = Query(None, description="Filter by target tool"),
    db: Session = Depends(get_session)
):
    """
    Query action logs with filters.
    
    This endpoint provides access to the immutable audit log for compliance
    and troubleshooting. Supports filtering by date range, action type, result,
    and tools involved.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (1-1000)
        start_date: Filter logs after this date
        end_date: Filter logs before this date
        action: Filter by action type (create_ticket, update_status, link_items, sync_error)
        result: Filter by result (success, failed, conflict)
        source_tool: Filter by source tool
        target_tool: Filter by target tool
        db: Database session dependency
        
    Returns:
        Dictionary with logs list and pagination metadata
    """
    try:
        # Build query
        query = db.query(ActionLog)
        
        # Apply date filters
        if start_date:
            query = query.filter(ActionLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(ActionLog.timestamp <= end_date)
        
        # Apply action filter
        if action:
            valid_actions = ["create_ticket", "update_status", "link_items", "sync_error"]
            if action not in valid_actions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"
                )
            query = query.filter(ActionLog.action == action)
        
        # Apply result filter
        if result:
            valid_results = ["success", "failed", "conflict"]
            if result not in valid_results:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid result: {result}. Must be one of: {', '.join(valid_results)}"
                )
            query = query.filter(ActionLog.result == result)
        
        # Apply tool filters
        if source_tool:
            query = query.filter(ActionLog.source_tool == source_tool)
        
        if target_tool:
            query = query.filter(ActionLog.target_tool == target_tool)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering (most recent first)
        logs = query.order_by(ActionLog.timestamp.desc()).offset(skip).limit(limit).all()
        
        logger.info(
            f"Retrieved {len(logs)} log entries "
            f"(skip={skip}, limit={limit}, total={total_count})"
        )
        
        return {
            "logs": [log.to_dict() for log in logs],
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total_count,
                "returned": len(logs)
            },
            "filters": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "action": action,
                "result": result,
                "source_tool": source_tool,
                "target_tool": target_tool
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve logs: {str(e)}"
        )
