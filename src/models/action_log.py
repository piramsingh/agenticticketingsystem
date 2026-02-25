"""ActionLog database model for immutable audit trail"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class ActionLog(Base):
    """
    Immutable audit log for all sync actions.
    Required for regulatory compliance (FDA 21 CFR Part 11).
    
    Attributes:
        id: Primary key
        timestamp: When the action occurred
        action: Type of action (create_ticket, update_status, link_items, sync_error)
        source_tool: Source system for the action
        source_item_id: Source item ID
        target_tool: Target system for the action
        target_item_id: Target item ID
        payload: Full JSON payload with before/after states
        result: Result of the action (success, failed, conflict)
        error_detail: Error details if result is failed or conflict
    """
    __tablename__ = "action_log"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    source_tool: Mapped[str] = mapped_column(String(50), nullable=False)
    source_item_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_tool: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_item_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        CheckConstraint(
            "action IN ('create_ticket', 'update_status', 'link_items', 'sync_error')",
            name='ck_action_type'
        ),
        CheckConstraint(
            "result IN ('success', 'failed', 'conflict')",
            name='ck_result_type'
        ),
        Index('idx_action_log_timestamp', 'timestamp'),
        Index('idx_action_log_action', 'action'),
        Index('idx_action_log_result', 'result'),
    )
    
    def __setattr__(self, key, value):
        """
        Prevent updates to ActionLog entries after creation.
        Enforces immutability at application level.
        """
        # Allow setting attributes during initialization (when id is None)
        if hasattr(self, 'id') and self.id is not None:
            raise ValueError("ActionLog entries are immutable and cannot be modified")
        super().__setattr__(key, value)
    
    def to_dict(self) -> dict:
        """Convert model to dictionary for API responses"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action": self.action,
            "source_tool": self.source_tool,
            "source_item_id": self.source_item_id,
            "target_tool": self.target_tool,
            "target_item_id": self.target_item_id,
            "payload": self.payload,
            "result": self.result,
            "error_detail": self.error_detail,
        }
