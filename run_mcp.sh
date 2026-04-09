#!/bin/bash
# Wrapper so MCP Inspector doesn't choke on the space in the project path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/mcp_server.py"
