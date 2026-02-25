# Jama Connect Agentic Sync Layer

A Python-based bidirectional synchronization agent that connects Jama Connect (requirements management) with external ticket management tools like Azure DevOps, GitLab, or Jira.

## Overview

This sync agent automates the bridge between Jama Connect and development tools, eliminating manual ticket creation and status updates while maintaining a comprehensive audit trail for regulatory compliance (FDA 21 CFR Part 11).

### Key Features

- **Bidirectional Sync**: Automatically sync requirements from Jama to tickets in target tools and status updates back to Jama
- **Conflict Detection**: Detects when both systems are modified between sync cycles and flags for manual resolution
- **Audit Trail**: Immutable action log for regulatory compliance
- **Extensible Connectors**: Abstract connector interface for easy addition of new target tools
- **Rate Limiting**: Respects Jama API rate limits with exponential backoff
- **REST API**: Management endpoints for monitoring and troubleshooting

## Architecture

- **FastAPI** web server for webhook reception and management API
- **APScheduler** for periodic polling of Jama activity stream
- **SQLite** database for sync mappings and audit logs
- **SQLAlchemy** ORM for database operations
- **Pydantic** for configuration validation

## Installation

### Prerequisites

- Python 3.11 or later
- Jama Connect instance with API access
- Target tool (Azure DevOps, GitLab, or Jira) with API access

### Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Copy the example configuration:
   ```bash
   cp config.example.yaml config.yaml
   ```

4. Edit `config.yaml` with your Jama and target tool credentials

5. Set environment variables for sensitive credentials:
   ```bash
   export JAMA_PASSWORD="your-jama-password"
   export ADO_PAT="your-azure-devops-pat"
   ```

## Configuration

Edit `config.yaml` to configure:
- Jama Connect connection settings
- Target tool connection settings
- Status mappings between systems
- Field mappings
- Polling interval
- Sync direction (bidirectional, jama_to_target, or target_to_jama)

See `config.example.yaml` for a complete example.

## Running

### Local Development

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t jama-sync-agent .
docker run -p 8000:8000 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/data:/app/data \
  -e JAMA_PASSWORD="${JAMA_PASSWORD}" \
  -e ADO_PAT="${ADO_PAT}" \
  jama-sync-agent
```

### Docker Compose

```bash
docker-compose up
```

## API Endpoints

- `GET /health` - Health check with sync status
- `GET /mappings` - List all sync mappings (paginated)
- `GET /mappings/{jama_item_id}` - Get specific mapping
- `GET /logs` - Query audit logs with filters
- `POST /webhooks/{tool_name}` - Receive webhooks from target tools
- `POST /sync/trigger` - Manually trigger a sync cycle

## Testing

Run tests with:
```bash
pytest
```

With coverage:
```bash
pytest --cov=src --cov-report=html
```

## Project Structure

```
jama-sync-agent/
├── src/
│   ├── main.py              # FastAPI app and scheduler
│   ├── config.py            # Configuration management
│   ├── database.py          # Database setup
│   ├── models/              # SQLAlchemy models
│   ├── clients/             # API clients
│   │   ├── jama_client.py
│   │   └── connectors/      # Target tool connectors
│   ├── sync/                # Sync engine
│   │   ├── poller.py
│   │   ├── mapper.py
│   │   └── engine.py
│   └── api/                 # API endpoints
├── tests/                   # Test suite
├── config.example.yaml      # Example configuration
├── pyproject.toml          # Project dependencies
└── Dockerfile              # Container definition
```

## License

MIT
