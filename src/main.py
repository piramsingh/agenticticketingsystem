"""Main FastAPI application entry point."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import load_config
from .database import init_db, get_session_factory
from .connectors.factory import build as build_connector
from .sync.engine import SyncEngine
from .sync.mapper import FieldMapper
from .sync.poller import ConnectorPoller
from .api import webhooks, health, mappings, logs, chat, tickets, status, scan
from .agent.chat_agent import ChatAgent
from .agent.ticket_parser import LLMTicketParser

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None
poller: ConnectorPoller | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global scheduler, poller

    logger.info("Starting Ticket Agent...")

    try:
        # Load config (supports any tool via connectors list)
        config_path = os.getenv("CONFIG_PATH", "config.yaml")
        logger.info("Loading configuration from %s", config_path)
        config = load_config(config_path)
        logger.info(
            "Configuration loaded: source=%s, target=%s",
            config.sync.source, config.sync.target,
        )

        # Database
        database_path = os.getenv("DATABASE_PATH", "data/sync.db")
        logger.info("Initialising database at %s", database_path)
        init_db(database_path)

        # Build connectors from config using the factory
        source_connector = build_connector(config.get_source_config())
        target_connector = build_connector(config.get_target_config())
        logger.info("Connectors built: %s → %s", config.sync.source, config.sync.target)

        # Validate target connection (quick health check)
        if await target_connector.validate_connection():
            logger.info("Target connector validated successfully")
        else:
            logger.warning("Target connector validation failed — continuing anyway")

        # Sync components
        mapper = FieldMapper(config)
        session_factory = get_session_factory()
        db_session = session_factory()
        sync_engine = SyncEngine(
            db_session=db_session,
            source_connector=source_connector,
            target_connector=target_connector,
            mapper=mapper,
            config=config,
        )

        # Poller — works with any connector that implements get_activities()
        # If source == target (single-tool config), get_activities returns [] (no-op)
        poller = ConnectorPoller(source_connector, sync_engine)

        # Chat agent talks to the target connector
        parser = LLMTicketParser(api_key=os.getenv("OPENROUTER_API_KEY"))
        chat_agent = ChatAgent(parser=parser, connector=target_connector)

        # Wire up API dependencies
        webhooks.set_dependencies(sync_engine, target_connector)
        health.set_poller(poller)
        chat.set_chat_agent(chat_agent)
        tickets.set_connector(target_connector)
        status.set_connector(
            target_connector,
            connector_type=config.get_target_config().tool_type,
            project=config.get_target_config().project,
        )

        # Scheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            poller.poll,
            "interval",
            seconds=config.sync.polling_interval,
            id="connector_poll",
            name="Poll Source Connector Activities",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "Scheduler started — polling every %ds", config.sync.polling_interval
        )
        logger.info("Ticket Agent startup complete")

        yield

    except Exception as e:
        logger.error("Failed to start application: %s", e, exc_info=True)
        raise

    # Shutdown
    logger.info("Shutting down Ticket Agent...")
    try:
        if scheduler is not None:
            scheduler.shutdown(wait=True)
        if "db_session" in locals():
            db_session.close()
        if "source_connector" in locals():
            await source_connector.close()
        if "target_connector" in locals():
            await target_connector.close()
        logger.info("Ticket Agent shutdown complete")
    except Exception as e:
        logger.error("Error during shutdown: %s", e, exc_info=True)


app = FastAPI(
    title="Ticket Agent",
    description="Tool-agnostic AI ticketing agent with bidirectional sync",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception in %s %s: %s",
        request.method, request.url.path, exc, exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc), "path": request.url.path},
    )


app.include_router(webhooks.router)
app.include_router(health.router)
app.include_router(status.router)
app.include_router(mappings.router)
app.include_router(logs.router)
app.include_router(chat.router)
app.include_router(tickets.router)
app.include_router(scan.router)


@app.get("/")
async def root():
    return {
        "name": "Ticket Agent",
        "version": "0.2.0",
        "description": "Tool-agnostic AI ticketing agent with bidirectional sync",
        "endpoints": {
            "health":        "/health",
            "webhooks":      "/webhooks/{tool_name}",
            "mappings":      "/mappings",
            "logs":          "/logs",
            "trigger_sync":  "/webhooks/sync/trigger",
            "chat":          "/chat",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
