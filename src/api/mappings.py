"""Mapping query endpoints for monitoring sync relationships"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models.mapping import SyncMapping


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.get("")
async def list_mappings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    sync_status: Optional[str] = Query(None, description="Filter by sync status (active, conflict, error)"),
    target_tool: Optional[str] = Query(None, description="Filter by target tool"),
    db: Session = Depends(get_session)
):
    """
    List all sync mappings with pagination and filtering.
    
    This endpoint returns a paginated list of sync mappings between Jama items
    and target tool items. Supports filtering by sync status and target tool.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (1-1000)
        sync_status: Optional filter by sync status
        target_tool: Optional filter by target tool
        db: Database session dependency
        
    Returns:
        Dictionary with mappings list and pagination metadata
    """
    try:
        # Build query
        query = db.query(SyncMapping)
        
        # Apply filters
        if sync_status:
            if sync_status not in ["active", "conflict", "error"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid sync_status: {sync_status}. Must be one of: active, conflict, error"
                )
            query = query.filter(SyncMapping.sync_status == sync_status)
        
        if target_tool:
            query = query.filter(SyncMapping.target_tool == target_tool)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        mappings = query.order_by(SyncMapping.created_at.desc()).offset(skip).limit(limit).all()
        
        logger.info(
            f"Retrieved {len(mappings)} mappings "
            f"(skip={skip}, limit={limit}, total={total_count})"
        )
        
        return {
            "mappings": [mapping.to_dict() for mapping in mappings],
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total_count,
                "returned": len(mappings)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list mappings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mappings: {str(e)}"
        )


@router.get("/{jama_item_id}")
async def get_mapping(
    jama_item_id: int,
    target_tool: Optional[str] = Query(None, description="Target tool to filter by"),
    db: Session = Depends(get_session)
):
    """
    Get mapping for specific Jama item.
    
    This endpoint retrieves the sync mapping for a specific Jama item.
    If target_tool is specified, returns only the mapping for that tool.
    Otherwise, returns all mappings for the Jama item.
    
    Args:
        jama_item_id: Jama item ID to look up
        target_tool: Optional target tool filter
        db: Database session dependency
        
    Returns:
        Mapping dictionary or list of mappings
        
    Raises:
        HTTPException: If mapping not found (404)
    """
    try:
        # Build query
        query = db.query(SyncMapping).filter(
            SyncMapping.jama_item_id == jama_item_id
        )
        
        if target_tool:
            query = query.filter(SyncMapping.target_tool == target_tool)
            mapping = query.first()
            
            if not mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Mapping not found for Jama item {jama_item_id} and tool {target_tool}"
                )
            
            logger.info(
                f"Retrieved mapping for Jama item {jama_item_id} "
                f"and tool {target_tool}"
            )
            
            return mapping.to_dict()
        else:
            # Return all mappings for this Jama item
            mappings = query.all()
            
            if not mappings:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No mappings found for Jama item {jama_item_id}"
                )
            
            logger.info(
                f"Retrieved {len(mappings)} mappings for Jama item {jama_item_id}"
            )
            
            return {
                "jama_item_id": jama_item_id,
                "mappings": [mapping.to_dict() for mapping in mappings]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get mapping for Jama item {jama_item_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mapping: {str(e)}"
        )
