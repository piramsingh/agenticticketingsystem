"""Tests for main FastAPI application"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    from src.config import (
        AppConfig, JamaConfig, TargetToolConfig, 
        SyncConfig, StatusMappingItem
    )
    from pydantic import SecretStr
    
    return AppConfig(
        jama=JamaConfig(
            base_url="https://test.jamacloud.com",
            username="test_user",
            password=SecretStr("test_password"),
            project_id=12345
        ),
        target_tool=TargetToolConfig(
            tool_type="azure_devops",
            base_url="https://dev.azure.com/test",
            pat=SecretStr("test_pat"),
            project="TestProject"
        ),
        sync=SyncConfig(
            polling_interval=60,
            direction="bidirectional"
        ),
        status_mappings=[
            StatusMappingItem(jama="Draft", target="New"),
            StatusMappingItem(jama="Approved", target="Active")
        ],
        field_mappings={
            "name": "title",
            "description": "description",
            "priority": "priority",
            "status": "state"
        }
    )


@pytest.mark.asyncio
async def test_app_structure():
    """Test that the FastAPI app is properly structured"""
    from src.main import app
    
    # Verify app is created
    assert app is not None
    assert app.title == "Jama Sync Agent"
    assert app.version == "0.1.0"
    
    # Verify routes are registered
    routes = [route.path for route in app.routes]
    
    # Check that key endpoints exist
    assert "/" in routes
    assert "/health" in routes
    assert "/webhooks/{tool_name}" in routes
    assert "/mappings" in routes
    assert "/mappings/{jama_item_id}" in routes
    assert "/logs" in routes


def test_root_endpoint(mock_config):
    """Test the root endpoint returns API information"""
    from src.main import app
    from contextlib import asynccontextmanager
    
    # Create a mock lifespan that does nothing
    @asynccontextmanager
    async def mock_lifespan(app):
        yield
    
    # Replace the lifespan with our mock
    app.router.lifespan_context = mock_lifespan
    
    # Create test client
    with TestClient(app) as client:
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Jama Sync Agent"
        assert data["version"] == "0.1.0"
        assert "endpoints" in data
        assert "health" in data["endpoints"]


@pytest.mark.asyncio
async def test_global_exception_handler():
    """Test that global exception handler catches unexpected errors"""
    from src.main import app, global_exception_handler
    from fastapi import Request
    
    # Create a mock request
    mock_request = Mock(spec=Request)
    mock_request.method = "GET"
    mock_request.url.path = "/test"
    
    # Create a test exception
    test_exception = Exception("Test error")
    
    # Call the exception handler
    response = await global_exception_handler(mock_request, test_exception)
    
    # Verify response
    assert response.status_code == 500
    assert "error" in response.body.decode()


def test_main_imports():
    """Test that all required imports are available"""
    # This test verifies that the main module can be imported
    # and all its dependencies are available
    try:
        from src.main import (
            app, lifespan, global_exception_handler, root
        )
        assert app is not None
        assert lifespan is not None
        assert global_exception_handler is not None
        assert root is not None
    except ImportError as e:
        pytest.fail(f"Failed to import main module components: {e}")


@pytest.mark.asyncio
async def test_lifespan_startup_with_mocks(mock_config):
    """Test lifespan startup with mocked dependencies"""
    from src.main import lifespan, app
    
    # Mock all the dependencies
    with patch('src.main.load_config', return_value=mock_config), \
         patch('src.main.init_db'), \
         patch('src.main.JamaClient') as mock_jama_client, \
         patch('src.main.AzureDevOpsConnector') as mock_connector, \
         patch('src.main.FieldMapper'), \
         patch('src.main.get_session_factory') as mock_session_factory, \
         patch('src.main.SyncEngine'), \
         patch('src.main.JamaPoller'), \
         patch('src.main.AsyncIOScheduler') as mock_scheduler:
        
        # Set up mock returns
        mock_connector_instance = Mock()
        mock_connector_instance.validate_connection = AsyncMock(return_value=True)
        mock_connector.return_value = mock_connector_instance
        
        mock_session = Mock()
        mock_session_factory.return_value = Mock(return_value=mock_session)
        
        mock_scheduler_instance = Mock()
        mock_scheduler.return_value = mock_scheduler_instance
        
        # Test lifespan context manager
        try:
            async with lifespan(app):
                # Verify scheduler was started
                mock_scheduler_instance.start.assert_called_once()
        except Exception as e:
            # If there's an error, it should be from our mocks, not the actual code
            pytest.fail(f"Lifespan startup failed: {e}")
        
        # Verify scheduler was shut down
        mock_scheduler_instance.shutdown.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
