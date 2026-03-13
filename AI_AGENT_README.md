# 🤖 AI-Powered Ticket Creation Agent

## Overview

This system combines **AI-powered natural language understanding** with **automated bidirectional sync** to create a seamless ticket management experience.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                            │
│  "Create a ticket for Jamie to fix the security issue"      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI CHAT AGENT                              │
│  • Parses natural language                                   │
│  • Extracts: assignee, priority, type, labels               │
│  • Creates structured ticket data                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              TICKET CREATION LAYER                           │
│  • Creates ticket in Azure DevOps/Jira                       │
│  • Creates corresponding Jama requirement                    │
│  • Links them together                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           BIDIRECTIONAL SYNC SYSTEM                          │
│  • Keeps Jama ↔ Azure DevOps in sync                        │
│  • Detects conflicts                                         │
│  • Maintains audit trail                                     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Run the Interactive Chat Demo

```bash
cd agenticticketingsystem
python demo/chat_demo.py
```

Choose option 1 for interactive mode, then try:

```
You: Create a ticket for Jamie to fix the security issue in the backend

🤖 Processing...

✅ Created ticket #1000
   Assigned to: Jamie
   Priority: Medium
   Type: Bug
   URL: https://dev.azure.com/demo-org/DemoProject/_workitems/edit/1000

✅ Created Jama requirement #999
   Status: Draft

🔄 Backend sync system will keep them in sync automatically
```

### Run Example Scenarios

```bash
cd agenticticketingsystem
echo "2" | python demo/chat_demo.py
```

This runs 5 pre-defined scenarios showing different ticket types.

## Natural Language Examples

The AI agent understands various ways to describe tickets:

### Basic Ticket Creation
```
"Create a ticket to fix the login bug"
"Write a task for updating documentation"
"Add a feature request for dark mode"
```

### With Assignee
```
"Create a ticket for Jamie to fix the security issue"
"Assign Sarah to implement the new dashboard"
"Write a bug for @alex about the database error"
```

### With Priority
```
"Create a high priority bug for the login problem"
"Make a critical task to update the schema"
"Add a low priority feature request"
```

### With Labels/Tags
```
"Create a ticket to fix the backend security issue #security #backend"
"Write a task for the frontend redesign #frontend #ui"
```

### Complex Examples
```
"Create a critical bug ticket assigned to Jamie to fix the security vulnerability in the authentication backend #security #backend"

"Write a high priority user story for Sarah to implement the new dashboard with real-time analytics #frontend #feature"
```

## What the Agent Understands

### Assignees
- `"for Jamie"` → Assigned to: Jamie
- `"assigned to Sarah"` → Assigned to: Sarah
- `"@alex"` → Assigned to: Alex

### Priority
- `"critical"`, `"urgent"` → Critical
- `"high"`, `"important"` → High
- `"medium"`, `"normal"` → Medium (default)
- `"low"`, `"minor"` → Low

### Ticket Types
- `"bug"`, `"issue"`, `"fix"` → Bug
- `"feature"`, `"enhancement"` → Feature
- `"task"` → Task (default)
- `"user story"`, `"story"` → User Story

### Labels
- `#security` → security label
- `#backend` → backend label
- `#frontend` → frontend label
- `#database` → database label

## Components

### 1. Ticket Parser (`src/agent/ticket_parser.py`)

Extracts structured data from natural language:

```python
from src.agent import TicketParser

parser = TicketParser()
parsed = parser.parse("Create a high priority bug for Jamie")

print(parsed.title)      # "Create a bug for Jamie"
print(parsed.assignee)   # "Jamie"
print(parsed.priority)   # "High"
print(parsed.ticket_type) # "Bug"
```

### 2. Chat Agent (`src/agent/chat_agent.py`)

Orchestrates ticket creation:

```python
from src.agent import ChatAgent, TicketParser

agent = ChatAgent(
    parser=TicketParser(),
    connector=azure_connector,
    jama_client=jama_client,
    project_id=12345
)

result = await agent.process_message(
    "Create a ticket for Jamie to fix the security issue"
)

print(result["success"])  # True
print(result["target_ticket"]["id"])  # "1000"
```

### 3. Mock Clients (for demo)

- `demo/mock_jama_client.py` - Simulates Jama API
- `demo/mock_azure_connector.py` - Simulates Azure DevOps API

## Integration with Backend Sync

The AI agent creates tickets, then the backend sync system takes over:

1. **User creates ticket via chat**: "Create a ticket for Jamie..."
2. **AI agent creates**:
   - Azure DevOps work item
   - Jama requirement
3. **Backend sync system**:
   - Monitors both systems for changes
   - Keeps them in sync automatically
   - Detects conflicts
   - Maintains audit trail

## Production Deployment

### With Real APIs

1. **Configure credentials** in `config.yaml`:
```yaml
jama:
  base_url: "https://your-org.jamacloud.com"
  username: "your_username"
  password: "${JAMA_PASSWORD}"
  project_id: 12345

target_tool:
  tool_type: "azure_devops"
  base_url: "https://dev.azure.com/your-org"
  pat: "${ADO_PAT}"
  project: "YourProject"
```

2. **Add chat endpoint** to FastAPI app:
```python
from src.agent import ChatAgent, TicketParser

@app.post("/chat")
async def chat(message: str):
    agent = ChatAgent(parser, connector, jama_client, project_id)
    result = await agent.process_message(message)
    return result
```

3. **Build a frontend**:
   - Web chat interface
   - Slack bot
   - Teams bot
   - CLI tool

### With LLM Integration

For better natural language understanding, integrate an LLM:

```python
from src.agent import LLMTicketParser

# With OpenAI
parser = LLMTicketParser(api_key="your-openai-key")

# With Anthropic Claude
parser = LLMTicketParser(api_key="your-anthropic-key")

agent = ChatAgent(parser, connector, jama_client, project_id)
```

## API Endpoints

Once integrated with the main app, you can use:

### Create Ticket via Chat
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a ticket for Jamie to fix the security issue"}'
```

### Check Sync Status
```bash
curl http://localhost:8000/health
```

### View Created Mappings
```bash
curl http://localhost:8000/mappings
```

### View Audit Logs
```bash
curl http://localhost:8000/logs
```

## Testing

### Run Chat Demo Tests
```bash
pytest tests/test_ticket_parser.py -v
pytest tests/test_chat_agent.py -v
```

### Test Parser
```python
from src.agent import TicketParser

parser = TicketParser()

# Test assignee extraction
parsed = parser.parse("Create a ticket for Jamie")
assert parsed.assignee == "Jamie"

# Test priority extraction
parsed = parser.parse("Create a high priority bug")
assert parsed.priority == "High"
assert parsed.ticket_type == "Bug"
```

## Extending the Agent

### Add New Ticket Types
```python
# In ticket_parser.py
self.type_keywords = {
    "bug": "Bug",
    "feature": "Feature",
    "task": "Task",
    "epic": "Epic",  # Add new type
    "spike": "Spike"  # Add new type
}
```

### Add Custom Field Extraction
```python
def _extract_due_date(self, text: str) -> Optional[str]:
    """Extract due date from text"""
    # Pattern: "due by Friday", "deadline: 2024-03-15"
    patterns = [
        r"due\s+by\s+(\w+)",
        r"deadline:\s+(\d{4}-\d{2}-\d{2})"
    ]
    # ... implementation
```

### Add Multi-language Support
```python
class MultilingualParser(TicketParser):
    def parse(self, user_input: str, language: str = "en"):
        if language == "es":
            return self._parse_spanish(user_input)
        elif language == "fr":
            return self._parse_french(user_input)
        else:
            return super().parse(user_input)
```

## Troubleshooting

### Parser Not Extracting Correctly
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test specific patterns
parser = TicketParser()
parsed = parser.parse("your problematic input")
print(f"Extracted: {parsed.to_dict()}")
```

### Agent Not Creating Tickets
```python
# Check connector status
result = await connector.validate_connection()
print(f"Connector valid: {result}")

# Check Jama client
items = await jama_client.get_activities(since=datetime.now())
print(f"Jama accessible: {len(items)} activities")
```

## Future Enhancements

- [ ] LLM integration for better NLU
- [ ] Multi-language support
- [ ] Voice input support
- [ ] Slack/Teams bot integration
- [ ] Web chat interface
- [ ] Ticket templates
- [ ] Bulk ticket creation
- [ ] Smart suggestions based on history
- [ ] Sentiment analysis for priority
- [ ] Automatic label suggestion

## Files

- `src/agent/ticket_parser.py` - Natural language parser
- `src/agent/chat_agent.py` - Chat agent orchestrator
- `demo/chat_demo.py` - Interactive demo
- `AI_AGENT_README.md` - This file

## Support

For issues or questions:
1. Check the demo: `python demo/chat_demo.py`
2. Review logs in the output
3. Test parser: `python -c "from src.agent import TicketParser; print(TicketParser().parse('your input'))"`

---

**Ready to create tickets with AI?** Run `python demo/chat_demo.py` now!
