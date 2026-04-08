# Jama Sync Agent - Demo Guide

## 🎯 Quick Start

Run the interactive demo without any API credentials:

```bash
cd agenticticketingsystem
python demo/run_demo.py
```

## 📺 What You'll See

The demo runs three complete scenarios showcasing the sync system:

### Demo 1: Jama → Azure DevOps Sync
```
🔄 Polling Jama for activities...
[DEMO] MockJamaClient.get_activities() returned 1 activities
[DEMO] MockAzureDevOpsConnector.create_item() created item 1000

✅ Poll completed: 1 items processed

📊 Created 1 sync mappings:
   • Jama Item 102 → Azure DevOps Item 1000
     Status: active
```

**What's happening:**
- System polls Jama for new requirements
- Automatically creates Azure DevOps work items
- Stores sync mappings in database
- Logs everything to audit trail

### Demo 2: Azure DevOps → Jama Sync (Webhook)
```
📥 Simulating webhook from Azure DevOps...
   Work item 1000 status changed to 'Resolved'

✅ Webhook processed successfully
   Jama item 102 updated with status from Azure DevOps
```

**What's happening:**
- Azure DevOps sends webhook when work item changes
- System updates corresponding Jama requirement
- Demonstrates bidirectional sync

### Demo 3: Conflict Detection
```
⚠️  CONFLICT DETECTED!

📊 Mapping status updated:
   • Sync Status: conflict ⚠️
   • Action: Manual resolution required

📝 Conflict logged to audit trail
```

**What's happening:**
- Both systems modified the same item
- System detects conflict automatically
- Flags for manual resolution
- Prevents data loss

## 🔑 Key Features Demonstrated

✓ **Bidirectional Synchronization** - Changes flow both ways  
✓ **Automatic Ticket Creation** - No manual work needed  
✓ **Webhook Processing** - Real-time updates  
✓ **Conflict Detection** - Prevents data loss  
✓ **Immutable Audit Logging** - Full compliance trail (FDA 21 CFR Part 11)  
✓ **Field and Status Mapping** - Configurable transformations  

## 📁 Demo Files

- `demo/run_demo.py` - Main demo script
- `demo/mock_jama_client.py` - Simulates Jama API
- `demo/mock_azure_connector.py` - Simulates Azure DevOps API
- `demo/demo_config.yaml` - Demo configuration
- `demo/README.md` - Detailed demo documentation

## 🚀 Next Steps

### 1. Explore the Code
```bash
# View the sync engine logic
cat src/sync/engine.py

# View the field mapper
cat src/sync/mapper.py

# View API endpoints
cat src/api/health.py
```

### 2. Run Tests
```bash
pytest tests/ -v
```

### 3. Configure Real APIs

Edit `config.yaml`:
```yaml
jama:
  base_url: "https://your-org.jamacloud.com"
  username: "your_username"
  password: "${JAMA_PASSWORD}"  # Set environment variable
  project_id: 12345

target_tool:
  tool_type: "azure_devops"
  base_url: "https://dev.azure.com/your-org"
  pat: "${ADO_PAT}"  # Set environment variable
  project: "YourProject"
```

### 4. Run the Full Application
```bash
# Set environment variables
export JAMA_PASSWORD="your_password"
export ADO_PAT="your_pat_token"

# Start the application
uvicorn src.main:app --reload

# Access the API
open http://localhost:8000/docs
```

## 📊 API Endpoints

Once running, you can access:

- **Health Check**: `GET http://localhost:8000/health`
- **Mappings**: `GET http://localhost:8000/mappings`
- **Audit Logs**: `GET http://localhost:8000/logs`
- **Webhooks**: `POST http://localhost:8000/webhooks/azure_devops`
- **Manual Sync**: `POST http://localhost:8000/webhooks/sync/trigger`
- **API Docs**: `http://localhost:8000/docs`

## 🔍 Understanding the Output

### Sync Mappings
```
Jama Item 102 → Azure DevOps Item 1000
```
This shows which Jama requirement corresponds to which Azure DevOps work item.

### Audit Logs
```
create_ticket: jama → azure_devops (success)
```
Every action is logged for regulatory compliance.

### Conflict Status
```
Sync Status: conflict ⚠️
```
When both systems change the same item, manual resolution is required.

## 💡 Tips

- **No API Access Needed**: The demo uses mock data
- **In-Memory Database**: No persistent storage required
- **Safe to Run**: Won't make any real API calls
- **Repeatable**: Run as many times as you want

## 🐛 Troubleshooting

**Import errors?**
```bash
# Make sure you're in the right directory
cd agenticticketingsystem

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

**Want more details?**
```bash
# Read the full design document
cat .kiro/specs/jama-agentic-sync/design.md

# Check the requirements
cat .kiro/specs/jama-agentic-sync/requirements.md
```

## 📚 Additional Resources

- **Design Document**: `.kiro/specs/jama-agentic-sync/design.md`
- **Requirements**: `.kiro/specs/jama-agentic-sync/requirements.md`
- **Tasks**: `.kiro/specs/jama-agentic-sync/tasks.md`
- **Tests**: `tests/`
- **Demo README**: `demo/README.md`

---

**Ready to see it in action?** Run `python demo/run_demo.py` now!
