# Agentic Ticketing System — POC Demo

An AI-powered chat interface that creates Azure DevOps work items from plain English.

> **Live Azure project:** [dev.azure.com/piramsingh-demo/bio-rad demo](https://dev.azure.com/piramsingh-demo/bio-rad%20demo) — public, no login needed. Tickets you create will appear here in real time.

---

## What it does

Type a natural language message → the agent parses it → a real Azure DevOps work item is created.

```
"Create a high priority bug for the login page crashing"
"Mike needs a ticket to fix the API timeout issue"
"Add a task to update the documentation #backend"
```

The agent understands:
- **Priority** — "high priority", "critical", "urgent", "low"
- **Type** — "bug", "task", "feature", "issue"
- **Assignee** — "for Mike to fix", "assign to Sarah", "Mike needs a ticket", "@alex"
- **Labels** — "#backend", "#security", or keywords like "frontend", "database"

---

## Quick start

### Prerequisites
- Python 3.11+
- Git

### 1. Clone the repo (poc-demo branch)

```bash
git clone -b poc-demo https://github.com/piramsingh/agenticticketingsystem.git
cd agenticticketingsystem
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install fastapi uvicorn httpx python-dotenv sqlalchemy pydantic pydantic-settings
```

### 4. Set up credentials

Create a `.env` file in the project root:

```
AZURE_ORG_URL=https://dev.azure.com/piramsingh-demo
AZURE_PROJECT=bio-rad demo
AZURE_PAT=<ask Piram for the PAT>
```

> The Azure project is public so anyone can **view** tickets. You need the PAT to **create** them. Ask Piram for access.

### 5. Start the backend

```bash
source venv/bin/activate
python demo/run_webapp_demo.py
```

You should see:
```
🚀 Agentic Ticketing System is running!
Backend API: http://localhost:8000
```

### 6. Start the frontend (new terminal tab)

```bash
cd webapp
python -m http.server 8080
```

### 7. Open the app

Go to **http://localhost:8080** in your browser.

---

## Using the demo

1. Type a message in the chat box (or click one of the example chips)
2. Hit **Send** or press **Enter**
3. A ticket card appears with the work item ID and a direct link to Azure DevOps
4. Click **"View in Azure DevOps ↗"** to see the real ticket

---

## Project structure

```
agenticticketingsystem/
├── demo/
│   └── run_webapp_demo.py     # Demo server entrypoint
├── src/
│   ├── agent/
│   │   ├── chat_agent.py      # Orchestrates parsing → ticket creation
│   │   └── ticket_parser.py   # NLP: extracts title, assignee, priority, type
│   ├── clients/
│   │   └── connectors/
│   │       └── azure_devops.py  # Azure DevOps REST API client
│   └── api/
│       └── chat.py            # FastAPI /chat endpoint
└── webapp/
    ├── index.html             # Chat UI
    └── app.js                 # Frontend logic
```

---

## Troubleshooting

**"Could not reach the server"**
- Make sure the backend (`run_webapp_demo.py`) is running on port 8000
- Make sure the frontend (`python -m http.server 8080`) is running on port 8080

**"Failed to create ticket: Client error 400"**
- Check that your `.env` has the correct `AZURE_PAT`, `AZURE_ORG_URL`, and `AZURE_PROJECT`

**Assignee shows as Unassigned**
- The name you mentioned wasn't found in the Azure DevOps project members list
- Only members of the `bio-rad demo` project can be auto-assigned
