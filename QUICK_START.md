# 🚀 Quick Start - Agentic Ticketing System Web UI

## One-Line Start

```bash
cd agenticticketingsystem && ./start_webapp_demo.sh
```

Then open **http://localhost:8080** in your browser.

---

## What You'll See

A modern web interface with:
- 🎨 Purple gradient design
- 💬 AI chat for creating tickets
- 📊 Real-time activity feed
- ⚡ Quick example templates

---

## Try These Examples

Type in the chat:

```
Create a critical bug for Jamie to fix the SQL injection vulnerability
```

```
Add a feature request for dark mode assigned to Sarah
```

```
Write a high priority task to update the documentation
```

---

## What Happens

1. AI parses your natural language
2. Creates ticket in Azure DevOps (mock)
3. Creates requirement in Jama (mock)
4. Shows you the ticket details
5. Backend keeps them synced

---

## Manual Start (if script doesn't work)

**Terminal 1 - Backend:**
```bash
cd agenticticketingsystem
python3 demo/run_webapp_demo.py
```

**Terminal 2 - Frontend:**
```bash
cd agenticticketingsystem/webapp
python3 -m http.server 8080
```

**Browser:**
```
http://localhost:8080
```

---

## Troubleshooting

**"Command not found: python3"**
- Install Python 3.8+ from python.org

**"No module named 'fastapi'"**
```bash
cd agenticticketingsystem
pip3 install -e .
```

**"Port already in use"**
- Change ports in the commands above
- Update `API_BASE_URL` in `webapp/app.js`

---

## Learn More

- **Full Guide**: See `WEBAPP_DEMO_GUIDE.md`
- **API Docs**: http://localhost:8000/docs
- **Architecture**: See `WEBAPP_SUMMARY.md`

---

## Stop Servers

Press **Ctrl+C** in the terminal running the script.

---

**Ready to demo to customers!** 🎉
