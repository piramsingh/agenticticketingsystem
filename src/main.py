"""Main FastAPI application entry point"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import load_config
from .database import init_db, get_session_factory
from .clients.jama_client import JamaClient
from .clients.connectors.azure_devops import AzureDevOpsConnector
from .sync.engine import SyncEngine
from .sync.mapper import FieldMapper
from .sync.poller import JamaPoller
from .api import webhooks, health, mappings, logs, chat
from .agent.chat_agent import ChatAgent
from .agent.ticket_parser import TicketParser


# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global references for components
scheduler: AsyncIOScheduler | None = None
poller: JamaPoller | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown operations.
    
    Startup:
    - Load configuration from config.yaml
    - Initialize database and create tables
    - Initialize Jama client, connector, mapper, and sync engine
    - Set up APScheduler with polling job
    - Start scheduler
    
    Shutdown:
    - Stop scheduler gracefully
    """
    global scheduler, poller
    
    # Startup
    logger.info("Starting Jama Sync Agent...")
    
    try:
        # Load configuration
        config_path = os.getenv("CONFIG_PATH", "config.yaml")
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)
        logger.info(
            f"Configuration loaded: Jama project {config.jama.project_id}, "
            f"Target tool: {config.target_tool.tool_type}"
        )
        
        # Initialize database
        database_path = os.getenv("DATABASE_PATH", "data/sync.db")
        logger.info(f"Initializing database at {database_path}")
        init_db(database_path)
        logger.info("Database initialized successfully")
        
        # Initialize components
        logger.info("Initializing sync components...")
        
        # Create Jama client
        jama_client = JamaClient(config.jama)
        logger.info("Jama client initialized")
        
        # Create connector based on tool type
        if config.target_tool.tool_type == "azure_devops":
            connector = AzureDevOpsConnector(config.target_tool)
            logger.info("Azure DevOps connector initialized")
        else:
            raise ValueError(
                f"Unsupported tool type: {config.target_tool.tool_type}. "
                f"Only 'azure_devops' is currently supported."
            )
        
        # Validate connector connection
        logger.info("Validating target tool connection...")
        if await connector.validate_connection():
            logger.info("Target tool connection validated successfully")
        else:
            logger.warning("Target tool connection validation failed")
        
        # Create field mapper
        mapper = FieldMapper(config)
        logger.info("Field mapper initialized")
        
        # Create sync engine
        session_factory = get_session_factory()
        db_session = session_factory()
        sync_engine = SyncEngine(
            db_session=db_session,
            jama_client=jama_client,
            connector=connector,
            mapper=mapper,
            config=config
        )
        logger.info("Sync engine initialized")
        
        # Create poller
        poller = JamaPoller(jama_client, sync_engine)
        logger.info("Jama poller initialized")
        
        # Create chat agent
        parser = TicketParser()
        chat_agent = ChatAgent(
            parser=parser,
            connector=connector,
            jama_client=jama_client,
            project_id=config.jama.project_id
        )
        logger.info("Chat agent initialized")
        
        # Set dependencies for API endpoints
        webhooks.set_dependencies(sync_engine, connector)
        health.set_poller(poller)
        chat.set_chat_agent(chat_agent)
        logger.info("API endpoint dependencies configured")
        
        # Set up APScheduler
        scheduler = AsyncIOScheduler()
        polling_interval = config.sync.polling_interval
        
        logger.info(f"Configuring scheduler with {polling_interval}s polling interval")
        scheduler.add_job(
            poller.poll,
            'interval',
            seconds=polling_interval,
            id='jama_poll',
            name='Poll Jama Activities',
            replace_existing=True
        )
        
        # Start scheduler
        scheduler.start()
        logger.info("Scheduler started successfully")
        
        logger.info("Jama Sync Agent startup complete")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise
    
    # Shutdown
    logger.info("Shutting down Jama Sync Agent...")
    
    try:
        if scheduler is not None:
            scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")
        
        # Close database session
        if 'db_session' in locals():
            db_session.close()
            logger.info("Database session closed")
        
        logger.info("Jama Sync Agent shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title="Jama Sync Agent",
    description="Bidirectional synchronization between Jama Connect and ticket management tools",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for unexpected errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unexpected errors.
    
    Logs the error with full context and returns a 500 response.
    This ensures the application continues operating even when
    unexpected errors occur.
    """
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: {exc}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": request.url.path
        }
    )


# Mount API routers
app.include_router(webhooks.router)
app.include_router(health.router)
app.include_router(mappings.router)
app.include_router(logs.router)
app.include_router(chat.router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Jama Sync Agent",
        "version": "0.1.0",
        "description": "Bidirectional synchronization between Jama Connect and ticket management tools",
        "endpoints": {
            "health": "/health",
            "webhooks": "/webhooks/{tool_name}",
            "mappings": "/mappings",
            "logs": "/logs",
            "trigger_sync": "/webhooks/sync/trigger",
            "chat": "/chat"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
