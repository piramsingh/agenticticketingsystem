"""
Demo script for Jama Sync Agent

This script demonstrates the sync functionality using mock clients
that don't require real API access to Jama or Azure DevOps.

Run with: python demo/run_demo.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.database import init_db, get_session_factory
from src.sync.engine import SyncEngine
from src.sync.mapper import FieldMapper
from src.sync.poller import JamaPoller
from demo.mock_jama_client import MockJamaClient
from demo.mock_azure_connector import MockAzureDevOpsConnector


async def demo_jama_to_azure_sync(connector=None):
    """
    Demo 1: Jama → Azure DevOps sync
    
    Simulates polling Jama for new requirements and creating
    corresponding work items in Azure DevOps.
    """
    print("\n" + "="*70)
    print("DEMO 1: Jama → Azure DevOps Sync")
    print("="*70)
    print("Scenario: New requirements detected in Jama are automatically")
    print("          created as work items in Azure DevOps")
    print("="*70 + "\n")
    
    # Load config
    config = load_config("demo/demo_config.yaml")
    
    # Initialize database (in-memory for demo)
    init_db(":memory:")
    session_factory = get_session_factory()
    db_session = session_factory()
    
    # Create mock clients
    jama_client = MockJamaClient(config.jama)
    if connector is None:
        connector = MockAzureDevOpsConnector(config.target_tool)
    
    # Create mapper and sync engine
    mapper = FieldMapper(config)
    sync_engine = SyncEngine(
        db_session=db_session,
        jama_client=jama_client,
        connector=connector,
        mapper=mapper,
        config=config
    )
    
    # Create poller
    poller = JamaPoller(jama_client, sync_engine)
    
    # Run a poll cycle
    print("🔄 Polling Jama for activities...\n")
    result = await poller.poll()
    
    print(f"\n✅ Poll completed: {result.items_processed} items processed")
    
    # Show created mappings
    from src.models.mapping import SyncMapping
    mappings = db_session.query(SyncMapping).all()
    
    print(f"\n📊 Created {len(mappings)} sync mappings:")
    for mapping in mappings:
        print(f"   • Jama Item {mapping.jama_item_id} → Azure DevOps Item {mapping.target_item_id}")
        print(f"     Status: {mapping.sync_status}, URL: {mapping.target_item_url}")
    
    # Show action logs
    from src.models.action_log import ActionLog
    logs = db_session.query(ActionLog).all()
    
    print(f"\n📝 Audit log entries: {len(logs)}")
    for log in logs:
        print(f"   • {log.action}: {log.source_tool} → {log.target_tool} ({log.result})")
    
    db_session.close()
    return connector, mappings


async def demo_azure_to_jama_webhook():
    """
    Demo 2: Azure DevOps → Jama sync via webhook
    
    Simulates receiving a webhook from Azure DevOps when a work item
    is updated, and syncing that change back to Jama.
    """
    print("\n" + "="*70)
    print("DEMO 2: Azure DevOps → Jama Sync (Webhook)")
    print("="*70)
    print("Scenario: Work item updated in Azure DevOps triggers webhook")
    print("          that updates the corresponding Jama requirement")
    print("="*70 + "\n")
    
    # Load config
    config = load_config("demo/demo_config.yaml")
    
    # Initialize database (in-memory for demo)
    init_db(":memory:")
    session_factory = get_session_factory()
    db_session = session_factory()
    
    # Create mock clients
    jama_client = MockJamaClient(config.jama)
    connector = MockAzureDevOpsConnector(config.target_tool)
    
    # Create mapper and sync engine
    mapper = FieldMapper(config)
    sync_engine = SyncEngine(
        db_session=db_session,
        jama_client=jama_client,
        connector=connector,
        mapper=mapper,
        config=config
    )
    
    # First, create some mappings by polling Jama
    print("🔄 Initial sync: Creating mappings from Jama items...\n")
    poller = JamaPoller(jama_client, sync_engine)
    await poller.poll()
    
    # Get a mapping to simulate webhook for
    from src.models.mapping import SyncMapping
    mapping = db_session.query(SyncMapping).first()
    
    if not mapping:
        print("❌ No mappings found to demo webhook")
        return
    
    print(f"\n📥 Simulating webhook from Azure DevOps...")
    print(f"   Work item {mapping.target_item_id} status changed to 'Resolved'\n")
    
    # Simulate webhook payload
    webhook_payload = {
        "eventType": "workitem.updated",
        "resource": {
            "id": int(mapping.target_item_id),
            "fields": {
                "System.Title": "User shall be able to login",
                "System.State": "Resolved",
                "System.Description": "Updated description from Azure DevOps"
            }
        }
    }
    
    # Parse and process webhook
    event = connector.parse_webhook(webhook_payload)
    await sync_engine.process_target_update(event)
    
    print(f"\n✅ Webhook processed successfully")
    print(f"   Jama item {mapping.jama_item_id} updated with status from Azure DevOps")
    
    # Show updated action logs
    from src.models.action_log import ActionLog
    logs = db_session.query(ActionLog).filter_by(
        action="update_status",
        source_tool="azure_devops"
    ).all()
    
    print(f"\n📝 Webhook sync audit log:")
    for log in logs:
        print(f"   • {log.action}: {log.source_tool} → {log.target_tool} ({log.result})")
    
    db_session.close()


async def demo_conflict_detection():
    """
    Demo 3: Conflict detection
    
    Simulates a scenario where both Jama and Azure DevOps have been
    updated since the last sync, triggering conflict detection.
    """
    print("\n" + "="*70)
    print("DEMO 3: Conflict Detection")
    print("="*70)
    print("Scenario: Both Jama and Azure DevOps updated the same item")
    print("          System detects conflict and flags for manual resolution")
    print("="*70 + "\n")
    
    # Load config
    config = load_config("demo/demo_config.yaml")
    
    # Initialize database (in-memory for demo)
    init_db(":memory:")
    session_factory = get_session_factory()
    db_session = session_factory()
    
    # Create mock clients
    jama_client = MockJamaClient(config.jama)
    connector = MockAzureDevOpsConnector(config.target_tool)
    
    # Create mapper and sync engine
    mapper = FieldMapper(config)
    sync_engine = SyncEngine(
        db_session=db_session,
        jama_client=jama_client,
        connector=connector,
        mapper=mapper,
        config=config
    )
    
    # Create initial mappings
    print("🔄 Initial sync: Creating mappings...\n")
    poller = JamaPoller(jama_client, sync_engine)
    await poller.poll()
    
    # Get a mapping
    from src.models.mapping import SyncMapping
    from datetime import datetime, timedelta
    
    mapping = db_session.query(SyncMapping).first()
    
    if not mapping:
        print("❌ No mappings found")
        return
    
    # Simulate both sides being modified after last sync
    print(f"⚠️  Simulating conflict scenario...")
    print(f"   1. Jama item {mapping.jama_item_id} modified at {datetime.utcnow()}")
    print(f"   2. Azure DevOps item {mapping.target_item_id} also modified")
    print(f"   3. Last sync was at {mapping.last_synced_at}")
    
    # Set last_synced_at to past so both appear modified
    mapping.last_synced_at = datetime.utcnow() - timedelta(hours=3)
    db_session.commit()
    
    # Try to sync from Jama (should detect conflict)
    print(f"\n🔄 Attempting to sync from Jama...\n")
    jama_item = await jama_client.get_item(mapping.jama_item_id)
    target_item = await connector.get_item(mapping.target_item_id)
    
    # Check for conflict
    is_conflict = await sync_engine.detect_conflict(mapping, jama_item, target_item)
    
    if is_conflict:
        print(f"⚠️  CONFLICT DETECTED!")
        await sync_engine.handle_conflict(mapping, jama_item, target_item)
        
        # Refresh mapping
        db_session.refresh(mapping)
        
        print(f"\n📊 Mapping status updated:")
        print(f"   • Jama Item: {mapping.jama_item_id}")
        print(f"   • Azure DevOps Item: {mapping.target_item_id}")
        print(f"   • Sync Status: {mapping.sync_status} ⚠️")
        print(f"   • Action: Manual resolution required")
        
        # Show conflict log
        from src.models.action_log import ActionLog
        conflict_log = db_session.query(ActionLog).filter_by(
            result="conflict"
        ).first()
        
        if conflict_log:
            print(f"\n📝 Conflict logged to audit trail:")
            print(f"   • Action: {conflict_log.action}")
            print(f"   • Result: {conflict_log.result}")
            print(f"   • Error Detail: {conflict_log.error_detail}")
    
    db_session.close()


async def main():
    """Run all demos"""
    print("\n" + "="*70)
    print("🚀 JAMA SYNC AGENT - INTERACTIVE DEMO")
    print("="*70)
    print("This demo showcases the bidirectional sync functionality")
    print("using mock data (no real API access required)")
    print("="*70)
    
    # Create shared connector to persist items across demos
    from src.config import load_config
    config = load_config("demo/demo_config.yaml")
    shared_connector = MockAzureDevOpsConnector(config.target_tool)
    
    try:
        # Demo 1: Jama to Azure sync
        await demo_jama_to_azure_sync_with_connector(shared_connector)
        
        await asyncio.sleep(1)
        
        # Demo 2: Azure to Jama webhook
        await demo_azure_to_jama_webhook_with_connector(shared_connector)
        
        await asyncio.sleep(1)
        
        # Demo 3: Conflict detection
        await demo_conflict_detection_with_connector(shared_connector)
        
        print("\n" + "="*70)
        print("✅ DEMO COMPLETE!")
        print("="*70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Bidirectional synchronization")
        print("  ✓ Automatic ticket creation")
        print("  ✓ Webhook processing")
        print("  ✓ Conflict detection")
        print("  ✓ Immutable audit logging")
        print("  ✓ Field and status mapping")
        print("\nNext Steps:")
        print("  • Configure real API credentials in config.yaml")
        print("  • Run: uvicorn src.main:app --reload")
        print("  • Access API docs at: http://localhost:8000/docs")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


# Wrapper functions that accept shared connector
async def demo_jama_to_azure_sync_with_connector(connector):
    """Demo 1 with shared connector"""
    return await demo_jama_to_azure_sync(connector)


async def demo_azure_to_jama_webhook_with_connector(connector):
    """Demo 2 with shared connector - modified to use shared connector"""
    print("\n" + "="*70)
    print("DEMO 2: Azure DevOps → Jama Sync (Webhook)")
    print("="*70)
    print("Scenario: Work item updated in Azure DevOps triggers webhook")
    print("          that updates the corresponding Jama requirement")
    print("="*70 + "\n")
    
    # Load config
    config = load_config("demo/demo_config.yaml")
    
    # Initialize database (in-memory for demo)
    init_db(":memory:")
    session_factory = get_session_factory()
    db_session = session_factory()
    
    # Create mock clients - use shared connector
    jama_client = MockJamaClient(config.jama)
    
    # Create mapper and sync engine
    mapper = FieldMapper(config)
    sync_engine = SyncEngine(
        db_session=db_session,
        jama_client=jama_client,
        connector=connector,  # Use shared connector
        mapper=mapper,
        config=config
    )
    
    # First, create some mappings by polling Jama
    print("🔄 Initial sync: Creating mappings from Jama items...\n")
    poller = JamaPoller(jama_client, sync_engine)
    await poller.poll()
    
    # Get a mapping to simulate webhook for
    from src.models.mapping import SyncMapping
    mapping = db_session.query(SyncMapping).first()
    
    if not mapping:
        print("❌ No mappings found to demo webhook")
        return
    
    print(f"\n📥 Simulating webhook from Azure DevOps...")
    print(f"   Work item {mapping.target_item_id} status changed to 'Resolved'\n")
    
    # Simulate webhook payload
    webhook_payload = {
        "eventType": "workitem.updated",
        "resource": {
            "id": int(mapping.target_item_id),
            "fields": {
                "System.Title": "User shall be able to login",
                "System.State": "Resolved",
                "System.Description": "Updated description from Azure DevOps"
            }
        }
    }
    
    # Parse and process webhook
    event = connector.parse_webhook(webhook_payload)
    await sync_engine.process_target_update(event)
    
    print(f"\n✅ Webhook processed successfully")
    print(f"   Jama item {mapping.jama_item_id} updated with status from Azure DevOps")
    
    # Show updated action logs
    from src.models.action_log import ActionLog
    logs = db_session.query(ActionLog).filter_by(
        action="update_status",
        source_tool="azure_devops"
    ).all()
    
    print(f"\n📝 Webhook sync audit log:")
    for log in logs:
        print(f"   • {log.action}: {log.source_tool} → {log.target_tool} ({log.result})")
    
    db_session.close()


async def demo_conflict_detection_with_connector(connector):
    """Demo 3 with shared connector - modified to use shared connector"""
    print("\n" + "="*70)
    print("DEMO 3: Conflict Detection")
    print("="*70)
    print("Scenario: Both Jama and Azure DevOps updated the same item")
    print("          System detects conflict and flags for manual resolution")
    print("="*70 + "\n")
    
    # Load config
    config = load_config("demo/demo_config.yaml")
    
    # Initialize database (in-memory for demo)
    init_db(":memory:")
    session_factory = get_session_factory()
    db_session = session_factory()
    
    # Create mock clients - use shared connector
    jama_client = MockJamaClient(config.jama)
    
    # Create mapper and sync engine
    mapper = FieldMapper(config)
    sync_engine = SyncEngine(
        db_session=db_session,
        jama_client=jama_client,
        connector=connector,  # Use shared connector
        mapper=mapper,
        config=config
    )
    
    # Create initial mappings
    print("🔄 Initial sync: Creating mappings...\n")
    poller = JamaPoller(jama_client, sync_engine)
    await poller.poll()
    
    # Get a mapping
    from src.models.mapping import SyncMapping
    from datetime import datetime, timedelta
    
    mapping = db_session.query(SyncMapping).first()
    
    if not mapping:
        print("❌ No mappings found")
        return
    
    # Simulate both sides being modified after last sync
    print(f"⚠️  Simulating conflict scenario...")
    print(f"   1. Jama item {mapping.jama_item_id} modified at {datetime.now()}")
    print(f"   2. Azure DevOps item {mapping.target_item_id} also modified")
    print(f"   3. Last sync was at {mapping.last_synced_at}")
    
    # Set last_synced_at to past so both appear modified
    mapping.last_synced_at = datetime.now() - timedelta(hours=3)
    db_session.commit()
    
    # Try to sync from Jama (should detect conflict)
    print(f"\n🔄 Attempting to sync from Jama...\n")
    jama_item = await jama_client.get_item(mapping.jama_item_id)
    target_item = await connector.get_item(mapping.target_item_id)
    
    # Check for conflict
    is_conflict = await sync_engine.detect_conflict(mapping, jama_item, target_item)
    
    if is_conflict:
        print(f"⚠️  CONFLICT DETECTED!")
        await sync_engine.handle_conflict(mapping, jama_item, target_item)
        
        # Refresh mapping
        db_session.refresh(mapping)
        
        print(f"\n📊 Mapping status updated:")
        print(f"   • Jama Item: {mapping.jama_item_id}")
        print(f"   • Azure DevOps Item: {mapping.target_item_id}")
        print(f"   • Sync Status: {mapping.sync_status} ⚠️")
        print(f"   • Action: Manual resolution required")
        
        # Show conflict log
        from src.models.action_log import ActionLog
        conflict_log = db_session.query(ActionLog).filter_by(
            result="conflict"
        ).first()
        
        if conflict_log:
            print(f"\n📝 Conflict logged to audit trail:")
            print(f"   • Action: {conflict_log.action}")
            print(f"   • Result: {conflict_log.result}")
            print(f"   • Error Detail: {conflict_log.error_detail}")
    
    db_session.close()


if __name__ == "__main__":
    asyncio.run(main())
