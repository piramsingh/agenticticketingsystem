# Jama Sync Agent - Interactive Demo

This demo showcases the bidirectional synchronization functionality using mock data. No real API access to Jama Connect or Azure DevOps is required!

## What the Demo Shows

The demo runs three scenarios:

### 1. Jama → Azure DevOps Sync
- Polls Jama for new requirements
- Automatically creates corresponding work items in Azure DevOps
- Stores sync mappings in the database
- Logs all actions to the audit trail

### 2. Azure DevOps → Jama Sync (Webhook)
- Simulates receiving a webhook from Azure DevOps
- Updates the corresponding Jama requirement
- Demonstrates bidirectional synchronization

### 3. Conflict Detection
- Simulates both systems being updated simultaneously
- Detects the conflict automatically
- Flags the mapping for manual resolution
- Logs the conflict with full details

## Running the Demo

### Prerequisites
```bash
# Make sure you're in the project directory
cd agenticticketingsystem

# Activate your virtual environment (if using one)
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### Run the Demo
```bash
python demo/run_demo.py
```

## What You'll See

The demo will output:
- 🔄 Polling activities from Jama
- ✅ Items being synced
- 📊 Sync mappings created
- 📝 Audit log entries
- ⚠️ Conflict detection in action

Example output:
```
======================================================================
🚀 JAMA SYNC AGENT - INTERACTIVE DEMO
======================================================================

DEMO 1: Jama → Azure DevOps Sync
======================================================================
Scenario: New requirements detected in Jama are automatically
          created as work items in Azure DevOps
======================================================================

🔄 Polling Jama for activities...

[DEMO] MockJamaClient.get_activities() returned 3 activities
[DEMO] MockJamaClient.get_item(100) returned: User shall be able to login
[DEMO] MockAzureDevOpsConnector.create_item() created item 1000: User shall be able to login

✅ Poll completed: 3 items processed

📊 Created 3 sync mappings:
   • Jama Item 100 → Azure DevOps Item 1000
     Status: active, URL: https://dev.azure.com/demo-org/DemoProject/_workitems/edit/1000
   ...
```

## Mock Data

The demo uses hardcoded data:

**Mock Jama Requirements:**
- Item 100: "User shall be able to login" (Draft, High priority)
- Item 101: "System shall validate user credentials" (Approved, High priority)
- Item 102: "User shall receive error message on invalid login" (Draft, Medium priority)

**Mock Azure DevOps Work Items:**
- Created dynamically as Jama items are synced
- Stored in-memory (no real API calls)

## Key Features Demonstrated

✓ **Bidirectional Synchronization** - Changes flow both ways  
✓ **Automatic Ticket Creation** - New Jama items create Azure DevOps work items  
✓ **Webhook Processing** - Real-time updates from Azure DevOps  
✓ **Conflict Detection** - Prevents data loss when both sides change  
✓ **Immutable Audit Logging** - Full compliance trail (FDA 21 CFR Part 11)  
✓ **Field and Status Mapping** - Configurable transformations  

## Next Steps

After running the demo, you can:

1. **Explore the code** - See how mock clients simulate real APIs
2. **Modify the demo** - Add your own scenarios in `run_demo.py`
3. **Configure real APIs** - Update `config.yaml` with real credentials
4. **Run the full application** - `uvicorn src.main:app --reload`

## Files in This Demo

- `run_demo.py` - Main demo script with 3 scenarios
- `mock_jama_client.py` - Mock Jama Connect client
- `mock_azure_connector.py` - Mock Azure DevOps connector
- `demo_config.yaml` - Demo configuration (no real credentials needed)
- `README.md` - This file

## Troubleshooting

**Import errors?**
- Make sure you're running from the `agenticticketingsystem` directory
- Check that your virtual environment is activated

**Database errors?**
- The demo uses in-memory SQLite (`:memory:`)
- No persistent database is created

**Want to see more?**
- Check the test files in `tests/` for more examples
- Read the design document in `.kiro/specs/jama-agentic-sync/design.md`
