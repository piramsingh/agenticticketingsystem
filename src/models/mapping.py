"""SyncMapping database model"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class SyncMapping(Base):
    """
    Tracks mappings between Jama items and target tool items.
    
    Attributes:
        id: Primary key
        jama_item_id: Jama item ID
        jama_project_id: Jama project ID
        jama_item_type: Type of Jama item (e.g., "Requirement")
        target_tool: Target tool name (e.g., "azure_devops")
        target_item_id: Target tool item ID
        target_item_url: URL to target tool item
        last_synced_at: Timestamp of last successful sync
        sync_status: Current sync status (active, conflict, error)
        created_at: Timestamp when mapping was created
    """
    __tablename__ = "sync_mapping"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jama_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    jama_project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    jama_item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_tool: Mapped[str] = mapped_column(String(50), nullable=False)
    target_item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    target_item_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(nullable=False)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('jama_item_id', 'target_tool', name='uq_jama_item_target'),
        Index('idx_jama_item', 'jama_item_id'),
        Index('idx_target_item', 'target_tool', 'target_item_id'),
        Index('idx_sync_status', 'sync_status'),
    )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary for API responses"""
        return {
            "id": self.id,
            "jama_item_id": self.jama_item_id,
            "jama_project_id": self.jama_project_id,
            "jama_item_type": self.jama_item_type,
            "target_tool": self.target_tool,
            "target_item_id": self.target_item_id,
            "target_item_url": self.target_item_url,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "sync_status": self.sync_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
