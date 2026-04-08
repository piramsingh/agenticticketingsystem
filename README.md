# Ticket Agent

An AI-powered ticketing agent that creates and syncs work items across project management tools — from plain English.

Supports **Azure DevOps**, **Jira**, and **Jama Connect** out of the box. Adding a new tool takes one file and one line of code.

> **Live Azure project:** [dev.azure.com/piramsingh-demo/bio-rad demo](https://dev.azure.com/piramsingh-demo/bio-rad%20demo) — public, no login needed. Tickets you create will appear here in real time.

---

## What it does

Type a plain English message → AI parses it → real work item gets created in your tool of choice.

```
"Create a high priority bug for Jamie — login page crashes on Safari"
"Feature request for dark mode, assign to Sarah"
"Task to update the docs #backend"
```

The agent understands:
- **Priority** — "high priority", "critical", "urgent", "low"
- **Type** — "bug", "feature", "task", "user story"
- **Assignee** — "for Jamie", "assign to Sarah", "@alex"
- **Labels** — "#backend", "#security", "#frontend"

---

## How it works

```
You type a message
       ↓
  LLM Parser (Claude)
  extracts: title, assignee, priority, type, labels
       ↓
  Connector (Azure / Jira / Jama)
  translates fields to the tool's native format
       ↓
  Work item created via REST API
       ↓
  Sync engine keeps both tools in sync automatically
```

---

## Architecture

The system is built around three ideas:

**1. Tool-agnostic connectors**
Every tool (Azure DevOps, Jira, Jama) implements the same `BaseConnector` interface. The agent never knows which tool it's talking to.

**2. YAML config templates**
Point the agent at any tool by filling in a YAML file. No code changes needed.

**3. Factory pattern**
Adding a new tool = one new connector file + one `@register` line. Nothing else changes.

---

## Project structure

```
agenticticketingsystem/
├── src/
│   ├── connectors/              # One file per tool
│   │   ├── base.py              # Abstract interface all connectors implement
│   │   ├── azure_devops.py      # Azure DevOps REST API
│   │   ├── jira.py              # Jira Cloud REST API v3
│   │   ├── jama.py              # Jama Connect wrapper
│   │   └── factory.py           # Builds the right connector from config
│   ├── agent/
│   │   ├── chat_agent.py        # Orchestrates parsing → ticket creation
│   │   └── ticket_parser.py     # Claude-powered NLP parser
│   ├── sync/
│   │   ├── engine.py            # Bidirectional sync orchestration
│   │   ├── poller.py            # Polls source connector for changes
│   │   └── mapper.py            # Maps fields between tools
│   ├── models/
│   │   └── ticket.py            # Shared data models (tool-agnostic)
│   ├── api/                     # FastAPI routes (chat, webhooks, health)
│   ├── config.py                # Config schema + YAML loader
│   └── main.py                  # App entry point
├── templates/                   # Ready-to-use config templates
│   ├── azure-only.yaml          # Azure DevOps standalone
│   ├── jira-only.yaml           # Jira standalone
│   └── jira-jama-sync.yaml      # Bidirectional Jira ↔ Jama sync
├── mcp_server.py                # MCP server for Claude Code integration
├── vscode-extension/            # VS Code sidebar extension
├── run_tests.py                 # Full test suite
└── webapp/                      # Browser-based chat UI
```

---

## Quick start

### Prerequisites
- Python 3.11+
- An Azure DevOps, Jira, or Jama account

### 1. Clone and set up

```bash
git clone -b poc-demo https://github.com/piramsingh/agenticticketingsystem.git
cd agenticticketingsystem
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Pick a config template

Copy one of the templates from `templates/` to `config.yaml` in the project root and fill in your credentials:

**Azure DevOps:**
```bash
cp templates/azure-only.yaml config.yaml
export ADO_ORG=yourorg
export ADO_PROJECT=yourproject
export ADO_PAT=yourtoken
```

**Jira:**
```bash
cp templates/jira-only.yaml config.yaml
export JIRA_DOMAIN=yourcompany
export JIRA_PROJECT_KEY=PROJ
export JIRA_EMAIL=you@company.com
export JIRA_API_TOKEN=yourtoken
```

### 3. Start the backend

```bash
python demo/run_webapp_demo.py
```

### 4. Open the web UI

```bash
cd webapp && python -m http.server 8080
```

Go to **http://localhost:8080**

---

## Claude Code integration (MCP)

Add this to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "ticket-agent": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/agenticticketingsystem"
    }
  }
}
```

Then inside Claude Code you can say:
- *"Create a high priority bug for the login issue"*
- *"List my recent tickets"*
- *"Who's on the team?"*

---

## VS Code Extension

```bash
cd vscode-extension
npm install
npm run compile
```

Press `F5` in VS Code to launch the extension. A chat sidebar appears in the activity bar.

---

## Running tests

```bash
export AZURE_ORG_URL="https://dev.azure.com/yourorg"
export AZURE_PAT="yourtoken"
export AZURE_PROJECT="yourproject"
python run_tests.py
```

---

## Adding a new tool

1. Create `src/connectors/mytool.py` implementing `BaseConnector`
2. Register it in `src/connectors/factory.py`:

```python
@register("mytool")
def _build_mytool(cfg):
    return MyToolConnector(cfg.base_url, cfg.auth.token.get_secret_value(), cfg.project)
```

That's it. The rest of the app picks it up automatically.

---

## Troubleshooting

**"Unknown tool_type"** — Check that `tool_type` in your config matches one of: `azure_devops`, `jira`, `jama`

**"Environment variable not set"** — Make sure you've exported all the `${VAR}` placeholders your config template references

**"Connection validation failed"** — Double-check your API token has read/write access to work items

**Assignee shows as Unassigned** — The name you used wasn't found in the project's member list. Run `list_members` via MCP to see valid names
