# Agentic Ticketing System - Web UI

Modern B2B SaaS web interface for AI-powered ticket creation and management.

## Features

- 🤖 Natural language ticket creation
- ✨ Modern gradient-based design with SF Pro Display font
- 📊 Real-time sync status and activity monitoring
- 🎯 Quick example templates
- 📱 Responsive design for all devices

## Running the Web UI

### 1. Start the Backend Server

First, start the FastAPI backend server:

```bash
cd agenticticketingsystem
python -m src.main
```

The backend will run on `http://localhost:8000`

### 2. Serve the Frontend

You can serve the frontend using any static file server. Here are a few options:

**Option A: Python HTTP Server**
```bash
cd webapp
python -m http.server 8080
```

**Option B: Node.js http-server**
```bash
cd webapp
npx http-server -p 8080
```

**Option C: VS Code Live Server**
- Install the "Live Server" extension
- Right-click on `index.html` and select "Open with Live Server"

### 3. Open in Browser

Navigate to `http://localhost:8080` (or the port shown by your server)

## Usage

### Creating Tickets

Simply type natural language descriptions in the chat interface:

- "Create a ticket for Jamie to fix the security issue"
- "Write a high priority bug for the login problem"
- "Add a feature request for dark mode assigned to Sarah"

The AI will:
1. Parse your natural language input
2. Create a ticket in Azure DevOps (or Jira)
3. Create a corresponding Jama requirement
4. Link them together via the sync system

### Quick Examples

Click any of the example cards to populate the input field with a template.

## Architecture

```
┌─────────────┐
│   Browser   │
│  (webapp)   │
└──────┬──────┘
       │ HTTP/JSON
       ▼
┌─────────────┐
│   FastAPI   │
│  Backend    │
└──────┬──────┘
       │
       ├─► Chat Agent (NLP parsing)
       ├─► Azure DevOps Connector
       ├─► Jama Client
       └─► Sync Engine
```

## Configuration

The frontend connects to the backend at `http://localhost:8000` by default.

To change this, edit the `API_BASE_URL` constant in `app.js`:

```javascript
const API_BASE_URL = 'http://your-backend-url:port';
```

## Design System

The UI uses a modern B2B SaaS design with:

- **Colors**: Purple gradient primary (#667eea → #764ba2)
- **Typography**: SF Pro Display font family
- **Spacing**: Consistent 8px grid system
- **Shadows**: Layered elevation system
- **Animations**: Smooth transitions and micro-interactions

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Development

The webapp is built with vanilla HTML, CSS, and JavaScript - no build step required!

To modify:
- `index.html` - Structure and layout
- `styles.css` - Design system and styling
- `app.js` - Chat functionality and API integration
