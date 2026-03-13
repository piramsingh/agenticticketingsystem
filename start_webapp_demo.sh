#!/bin/bash

# Agentic Ticketing System - Web UI Demo Launcher
# This script starts both the backend and frontend servers

echo "=========================================="
echo "🤖 Agentic Ticketing System - Web UI Demo"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed"
    exit 1
fi

# Use venv python
PYTHON="$(dirname "$0")/venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    echo "❌ venv not found. Run: python3 -m venv venv && venv/bin/pip install fastapi uvicorn httpx pyyaml sqlalchemy apscheduler pydantic"
    exit 1
fi

echo "✅ Dependencies OK"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
echo "🚀 Starting backend server..."
"$PYTHON" demo/run_webapp_demo.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "🌐 Starting frontend server..."
cd webapp
python3 -m http.server 8080 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 2

echo ""
echo "=========================================="
echo "✅ Servers are running!"
echo "=========================================="
echo ""
echo "🌐 Web UI:     http://localhost:8080"
echo "🔧 Backend:    http://localhost:8000"
echo "📚 API Docs:   http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "=========================================="
echo ""

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
