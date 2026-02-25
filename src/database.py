"""Database setup and session management"""
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass


# Global engine and session factory
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine(database_path: str = "data/sync.db") -> Engine:
    """
    Create or return SQLAlchemy engine for SQLite.
    
    Args:
        database_path: Path to SQLite database file
        
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    
    if _engine is None:
        # Ensure data directory exists
        db_path = Path(database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine with SQLite
        _engine = create_engine(
            f"sqlite:///{database_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )
        
        # Enable foreign keys for SQLite
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    return _engine


def init_db(database_path: str = "data/sync.db") -> None:
    """
    Initialize database and create all tables if they don't exist.
    
    Args:
        database_path: Path to SQLite database file
    """
    engine = get_engine(database_path)
    
    # Import models to register them with Base
    from src.models.mapping import SyncMapping
    from src.models.action_log import ActionLog
    
    # Create all tables
    Base.metadata.create_all(bind=engine)


def get_session_factory() -> sessionmaker:
    """
    Get or create session factory.
    
    Returns:
        SQLAlchemy sessionmaker
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions.
    Creates a new session for each request and closes it after.
    
    Yields:
        SQLAlchemy Session instance
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
