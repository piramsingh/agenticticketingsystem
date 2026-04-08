#!/usr/bin/env python3
"""
MCP server for the agentic ticketing system.

Exposes four tools to Claude Code / any MCP host:
  • create_ticket       — natural language → work item in the configured tool
  • get_ticket          — fetch a work item by ID
  • list_recent_tickets — list the N most recently changed work items
  • list_members        — list project members for @mention autocomplete

Configuration:
  Reads from a YAML config file (default: config.yaml) via CONFIG_PATH env var.
  Falls back to raw env vars for backwards compatibility with Azure DevOps:
    AZURE_ORG_URL, AZURE_PAT, AZURE_PROJECT

Run:
    python mcp_server.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from src.agent.chat_agent import ChatAgent
from src.agent.ticket_parser import LLMTicketParser
from src.connectors.factory import build as build_connector
from src.config import load_config

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_server")

app = Server("ticket-agent")

_agent: ChatAgent | None = None


def _get_agent() -> ChatAgent:
    global _agent
    if _agent is not None:
        return _agent

    config_path = os.getenv("CONFIG_PATH", "config.yaml")

    # Prefer config file when it exists
    if Path(config_path).exists():
        config = load_config(config_path)
        target_cfg = config.get_target_config()
        connector = build_connector(target_cfg)
        logger.info("MCP agent built from config file: %s → %s", config_path, target_cfg.tool_type)
    else:
        # Fallback: raw env vars for Azure DevOps (backwards compat)
        required = ["AZURE_ORG_URL", "AZURE_PAT", "AZURE_PROJECT"]
        missing = [v for v in required if not os.getenv(v)]
        if missing:
            raise RuntimeError(
                f"No config.yaml found at '{config_path}' and missing env vars: {', '.join(missing)}. "
                "Either provide a config file (see templates/) or set the env vars."
            )
        from src.connectors.azure_devops import AzureDevOpsConnector
        connector = AzureDevOpsConnector(
            base_url=os.environ["AZURE_ORG_URL"],
            pat=os.environ["AZURE_PAT"],
            project=os.environ["AZURE_PROJECT"],
        )
        logger.info("MCP agent built from env vars (Azure DevOps)")

    parser = LLMTicketParser(api_key=os.getenv("ANTHROPIC_API_KEY"))
    _agent = ChatAgent(parser=parser, connector=connector)
    return _agent


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="create_ticket",
            description=(
                "Create a work item in the configured project management tool from a "
                "plain-English request. Understands assignees ('for Jamie', '@sarah'), "
                "priority ('high priority', 'critical'), ticket type ('bug', 'feature', "
                "'task', 'user story'), and labels (#security, #backend)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": (
                            "Natural language request, e.g. "
                            "'Create a high priority bug for Jamie — login is broken on Safari'"
                        ),
                    }
                },
                "required": ["description"],
            },
        ),
        types.Tool(
            name="get_ticket",
            description="Fetch the current state of a work item by its ID or key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Work item ID or key, e.g. '1234' or 'PROJ-42'",
                    }
                },
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="list_recent_tickets",
            description="List the most recently modified work items in the project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of tickets to return (default 10, max 50)",
                        "default": 10,
                    }
                },
            },
        ),
        types.Tool(
            name="list_members",
            description=(
                "List all members of the project. "
                "Use this to find who to @mention when creating a ticket."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        agent = _get_agent()
    except RuntimeError as e:
        return [types.TextContent(type="text", text=f"Configuration error: {e}")]

    if name == "create_ticket":
        description = arguments.get("description", "").strip()
        if not description:
            return [types.TextContent(type="text", text="Please provide a ticket description.")]
        result = await agent.process_message(description)
        return [types.TextContent(type="text", text=result["message"])]

    elif name == "get_ticket":
        ticket_id = str(arguments.get("ticket_id", "")).strip()
        if not ticket_id:
            return [types.TextContent(type="text", text="Please provide a ticket ID.")]
        try:
            ticket = await agent.connector.get_item(ticket_id)
            text = (
                f"**{ticket.item_id} — {ticket.title}**\n"
                f"Status: {ticket.status} | Priority: {ticket.priority}\n"
                f"Last modified: {ticket.last_modified.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Description: {ticket.description or '(none)'}"
            )
        except Exception as e:
            text = f"Could not fetch ticket {ticket_id}: {e}"
        return [types.TextContent(type="text", text=text)]

    elif name == "list_recent_tickets":
        limit = min(int(arguments.get("limit", 10)), 50)
        try:
            tickets = await agent.connector.list_items(limit)
        except Exception as e:
            return [types.TextContent(type="text", text=f"Could not list tickets: {e}")]

        if not tickets:
            return [types.TextContent(type="text", text="No tickets found.")]

        lines = [f"**{len(tickets)} most recent work items:**\n"]
        for t in tickets:
            lines.append(
                f"• **{t['id']}** {t['title']}\n"
                f"  Status: {t.get('status', t.get('state', ''))} | "
                f"Priority: {t['priority']} | Assigned: {t.get('assignedTo', 'Unassigned')}\n"
                f"  {t['url']}"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "list_members":
        try:
            members = await agent.connector.list_members()
        except Exception as e:
            return [types.TextContent(type="text", text=f"Could not fetch members: {e}")]

        if not members:
            return [types.TextContent(type="text", text="No members found in this project.")]

        lines = [f"**{len(members)} project member(s):**\n"]
        for m in members:
            display = m.get("displayName", "")
            lines.append(f"• **{display}**")
        lines.append("\nUse their name when creating a ticket, e.g. 'assign to Jamie'")
        return [types.TextContent(type="text", text="\n".join(lines))]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
