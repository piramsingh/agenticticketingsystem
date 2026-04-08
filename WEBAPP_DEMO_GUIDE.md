# Web UI Demo Guide

This guide shows you how to run the complete Agentic Ticketing System with the modern web interface.

## Overview

The web UI provides a beautiful, modern B2B SaaS interface for creating tickets using natural language. It features:

- 🎨 Modern gradient design with SF Pro Display font
- 🤖 AI-powered natural language processing
- ⚡ Real-time ticket creation
- 📊 Activity monitoring and sync status
- 🎯 Quick example templates

## Quick Start

### Step 1: Start the Backend

Open a terminal and run:

```bash
cd agenticticketingsystem
python demo/run_webapp_demo.py
```

You should see:
```
🚀 Agentic Ticketing System is running!
Backend API: http://localhost:8000
```

Keep this terminal running.

### Step 2: Start the Frontend

Open a **new terminal** and run:

```bash
cd agenticticketingsystem/webapp
python -m http.server 8080
```

You should see:
```
Serving HTTP on 0.0.0.0 port 8080 (http://0.0.0.0:8080/) ...
```

### Step 3: Open in Browser

Open your browser and navigate to:

```
http://localhost:8080
```

## Using the Web UI

### Creating Tickets

Type natural language descriptions in the chat interface:

**Example 1: Bug Report**
```
Create a critical bug for Jamie to fix the SQL injection vulnerability
```

**Example 2: Feature Request**
```
Add a feature request for dark mode assigned to Sarah
```

**Example 3: Task**
```
Create a task to update the documentation
```

**Example 4: User Story**
```
Write a user story for implementing the new dashboard
```

### What the AI Understands

The AI parser recognizes:

- **Assignees**: "for Jamie", "assigned to Sarah", "@alex"
- **Priority**: "high priority", "critical", "low priority", "medium"
- **Types**: "bug", "feature", "task", "user story"
- **Labels**: "#security", "#backend", "#frontend"

### Quick Examples

Click any of the example cards at the bottom to populate the input field with a template.

## What Happens Behind the Scenes

When you send a message:

1. **Frontend** sends your message to the backend API
2. **TicketParser** extracts structured data (assignee, priority, type, labels)
3. **ChatAgent** creates a ticket in Azure DevOps (mock)
4. **ChatAgent** creates a Jama requirement (mock)
5. **SyncEngine** links them together
6. **Frontend** displays the created ticket details

## Architecture

```
┌──────────────────┐
│   Web Browser    │
│  (localhost:8080)│
└────────┬─────────┘
         │ HTTP/JSON
         ▼
┌──────────────────┐
│  FastAPI Backend │
│  (localhost:8000)│
└────────┬─────────┘
         │
         ├─► TicketParser (NLP)
         ├─► ChatAgent (Orchestration)
         ├─► MockAzureDevOpsConnector
         └─► MockJamaClient
```

## Demo Data

The demo uses mock clients that simulate real API calls:

- **Mock Azure DevOps**: Creates tickets with IDs like `DEMO-1001`, `DEMO-1002`
- **Mock Jama**: Creates requirements with IDs like `999`, `1000`
- **In-Memory Database**: Stores mappings temporarily (resets on restart)

## Troubleshooting

### Backend won't start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**: Install dependencies
```bash
cd agenticticketingsystem
pip install -e .
```

### Frontend can't connect to backend

**Error**: "Failed to connect to server"

**Solution**: 
1. Check that backend is running on port 8000
2. Check browser console for CORS errors
3. Verify `API_BASE_URL` in `webapp/app.js` is `http://localhost:8000`

### Port already in use

**Error**: `OSError: [Errno 48] Address already in use`

**Solution**: Use a different port
```bash
# Backend
uvicorn demo.run_webapp_demo:app --port 8001

# Frontend
python -m http.server 8081
```

Then update `API_BASE_URL` in `webapp/app.js` to match.

## Customization

### Change Colors

Edit `webapp/styles.css`:

```css
:root {
    --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    /* Change to your brand colors */
}
```

### Change API Endpoint

Edit `webapp/app.js`:

```javascript
const API_BASE_URL = 'http://your-backend-url:port';
```

### Add More Examples

Edit `webapp/index.html` and add more example cards:

```html
<button class="example-card" onclick="useExample(this)">
    <div class="example-icon task">📋</div>
    <div class="example-content">
        <h4 class="example-title">Your Title</h4>
        <p class="example-text">"Your example text"</p>
    </div>
</button>
```

## Production Deployment

For production deployment:

1. **Backend**: Deploy FastAPI app to a cloud service (AWS, Azure, GCP)
2. **Frontend**: Deploy static files to a CDN or static hosting
3. **CORS**: Update CORS settings to allow only your frontend domain
4. **Environment**: Use real Jama and Azure DevOps credentials
5. **Database**: Use PostgreSQL or MySQL instead of SQLite

## Next Steps

- Integrate with real Jama Connect API
- Integrate with real Azure DevOps API
- Add user authentication
- Add ticket history and search
- Add bulk ticket creation
- Add ticket templates
- Add team collaboration features

## Support

For issues or questions:
- Check the main README.md
- Review the API documentation at http://localhost:8000/docs
- Check the demo logs in the terminal

Enjoy creating tickets with natural language! 🚀
