#!/usr/bin/env python3
"""
Demo script for running the Agentic Ticketing System web UI.

This script:
1. Starts the FastAPI backend with mock clients
2. Provides instructions for accessing the web UI
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from dotenv import load_dotenv
load_dotenv()

from src.config import AppConfig as Config, JamaConfig, TargetToolConfig, SyncConfig
from src.database import init_db, get_session_factory
from src.agent.chat_agent import ChatAgent
from src.agent.ticket_parser import TicketParser
from src.api import chat
from src.clients.connectors.azure_devops import AzureDevOpsConnector
from demo.mock_jama_client import MockJamaClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for demo"""
    logger.info("Starting Agentic Ticketing System Demo...")
    
    # Load Azure DevOps credentials from environment
    azure_org_url = os.environ["AZURE_ORG_URL"]
    azure_project = os.environ["AZURE_PROJECT"]
    azure_pat     = os.environ["AZURE_PAT"]

    config = Config(
        jama=JamaConfig(
            base_url="https://demo.jamacloud.com",
            username="demo",
            password="demo",
            project_id=123
        ),
        target_tool=TargetToolConfig(
            tool_type="azure_devops",
            base_url=azure_org_url,
            pat=azure_pat,
            project=azure_project
        ),
        sync=SyncConfig(
            polling_interval=60,
            batch_size=50
        ),
        status_mappings=[],
        field_mappings={}
    )

    # Initialize in-memory database
    init_db(":memory:")
    logger.info("In-memory database initialized")

    # Real Azure DevOps connector + mock Jama
    connector   = AzureDevOpsConnector(base_url=azure_org_url, pat=azure_pat, project=azure_project, work_item_type="Issue")
    jama_client = MockJamaClient(config.jama)
    logger.info("Clients initialized (real Azure DevOps + mock Jama)")
    
    # Create chat agent
    parser = TicketParser()
    chat_agent = ChatAgent(
        parser=parser,
        connector=connector,
        jama_client=jama_client,
        project_id=config.jama.project_id
    )
    logger.info("Chat agent initialized")
    
    # Set chat agent for API
    chat.set_chat_agent(chat_agent)
    
    logger.info("Demo startup complete!")
    logger.info("=" * 60)
    logger.info("🚀 Agentic Ticketing System is running!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Backend API: http://localhost:8000")
    logger.info("API Docs: http://localhost:8000/docs")
    logger.info("")
    logger.info("To access the Web UI:")
    logger.info("  1. Open a new terminal")
    logger.info("  2. cd agenticticketingsystem/webapp")
    logger.info("  3. python -m http.server 8080")
    logger.info("  4. Open http://localhost:8080 in your browser")
    logger.info("")
    logger.info("=" * 60)
    
    yield
    
    logger.info("Shutting down demo...")


# Create FastAPI app
app = FastAPI(
    title="Agentic Ticketing System Demo",
    description="AI-powered ticket creation with natural language",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount chat router
app.include_router(chat.router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Agentic Ticketing System Demo",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat",
            "help": "/chat/help",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🤖 Agentic Ticketing System - Web UI Demo")
    print("=" * 60)
    print("\nStarting backend server...\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
