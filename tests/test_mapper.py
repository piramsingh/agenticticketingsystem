"""Unit tests for field and status mapper"""
import pytest
from datetime import datetime

from src.config import AppConfig, JamaConfig, TargetToolConfig, SyncConfig, StatusMappingItem
from src.sync.mapper import FieldMapper
from src.models.data_models import JamaItem, TargetItem


@pytest.fixture
def test_config():
    """Create test configuration"""
    return AppConfig(
        jama=JamaConfig(
            base_url="https://jama.example.com",
            username="test_user",
            password="test_pass",
            project_id=100
        ),
        target_tool=TargetToolConfig(
            tool_type="azure_devops",
            base_url="https://dev.azure.com/org",
            pat="test_pat",
            project="TestProject"
        ),
        sync=SyncConfig(
            polling_interval=60,
            direction="bidirectional"
        ),
        status_mappings=[
            StatusMappingItem(jama="Draft", target="New"),
            StatusMappingItem(jama="Approved", target="Active"),
            StatusMappingItem(jama="Implemented", target="Resolved"),
            StatusMappingItem(jama="Verified", target="Closed")
        ],
        field_mappings={
            "name": "title",
            "description": "description",
            "priority": "priority",
            "status": "state"
        }
    )


@pytest.fixture
def mapper(test_config):
    """Create field mapper instance"""
    return FieldMapper(test_config)


@pytest.fixture
def sample_jama_item():
    """Create sample Jama item"""
    return JamaItem(
        id=12345,
        project_id=100,
        item_type="Requirement",
        name="User shall be able to login",
        description="The system shall provide a login form",
        status="Approved",
        priority="High",
        last_modified=datetime(2026, 2, 25, 10, 0, 0),
        fields={}
    )


@pytest.fixture
def sample_target_item():
    """Create sample target item"""
    return TargetItem(
        item_id="67890",
        title="User shall be able to login",
        description="The system shall provide a login form",
        status="Active",
        priority="High",
        last_modified=datetime(2026, 2, 25, 11, 0, 0),
        fields={}
    )


def test_map_jama_to_target_all_fields(mapper, sample_jama_item):
    """Test mapping all Jama fields to target format"""
    result = mapper.map_jama_to_target(sample_jama_item)
    
    assert result["title"] == "User shall be able to login"
    assert result["description"] == "The system shall provide a login form"
    assert result["priority"] == "High"
    assert result["state"] == "Active"  # Approved -> Active


def test_map_target_to_jama_all_fields(mapper, sample_target_item):
    """Test mapping all target fields to Jama format"""
    result = mapper.map_target_to_jama(sample_target_item)
    
    assert result["name"] == "User shall be able to login"
    assert result["description"] == "The system shall provide a login form"
    assert result["priority"] == "High"
    assert result["status"] == "Approved"  # Active -> Approved


def test_map_status_jama_to_target(mapper):
    """Test status mapping from Jama to target"""
    assert mapper.map_status("Draft", "jama_to_target") == "New"
    assert mapper.map_status("Approved", "jama_to_target") == "Active"
    assert mapper.map_status("Implemented", "jama_to_target") == "Resolved"
    assert mapper.map_status("Verified", "jama_to_target") == "Closed"


def test_map_status_target_to_jama(mapper):
    """Test status mapping from target to Jama"""
    assert mapper.map_status("New", "target_to_jama") == "Draft"
    assert mapper.map_status("Active", "target_to_jama") == "Approved"
    assert mapper.map_status("Resolved", "target_to_jama") == "Implemented"
    assert mapper.map_status("Closed", "target_to_jama") == "Verified"


def test_map_status_unmapped_status(mapper):
    """Test handling of unmapped status"""
    result = mapper.map_status("UnknownStatus", "jama_to_target")
    assert result is None


def test_map_status_invalid_direction(mapper):
    """Test handling of invalid direction"""
    result = mapper.map_status("Draft", "invalid_direction")
    assert result is None


def test_map_jama_to_target_with_custom_fields(mapper):
    """Test mapping Jama item with custom fields"""
    jama_item = JamaItem(
        id=12345,
        project_id=100,
        item_type="Requirement",
        name="Test Item",
        description="Test Description",
        status="Draft",
        priority="Medium",
        last_modified=datetime.now(),
        fields={"custom_field": "custom_value"}
    )
    
    result = mapper.map_jama_to_target(jama_item)
    
    assert result["title"] == "Test Item"
    assert result["state"] == "New"


def test_map_target_to_jama_with_custom_fields(mapper):
    """Test mapping target item with custom fields"""
    target_item = TargetItem(
        item_id="123",
        title="Test Item",
        description="Test Description",
        status="New",
        priority="Medium",
        last_modified=datetime.now(),
        fields={"custom_field": "custom_value"}
    )
    
    result = mapper.map_target_to_jama(target_item)
    
    assert result["name"] == "Test Item"
    assert result["status"] == "Draft"


def test_missing_field_handling(mapper, sample_jama_item, caplog):
    """Test that missing field mappings are logged and handled gracefully"""
    # This should work without errors even if some fields aren't mapped
    result = mapper.map_jama_to_target(sample_jama_item)
    
    # Should still have the mapped fields
    assert "title" in result
    assert "description" in result
