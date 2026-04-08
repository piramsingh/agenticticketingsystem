"""Tests for Jama client wrapper"""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.clients.jama_client import JamaClient, TokenBucketRateLimiter
from src.config import JamaConfig
from pydantic import SecretStr


@pytest.fixture
def jama_config():
    """Create test Jama configuration"""
    return JamaConfig(
        base_url="https://jama.example.com",
        username="test_user",
        password=SecretStr("test_password"),
        project_id=12345
    )


@pytest.fixture
def jama_client(jama_config):
    """Create Jama client with mocked py-jama-rest-client"""
    with patch('src.clients.jama_client.PyJamaClient'):
        client = JamaClient(jama_config)
        return client


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self):
        """Test that rate limiter allows requests within the limit"""
        limiter = TokenBucketRateLimiter(max_requests=10, time_window=1.0)
        
        # Should be able to acquire 10 tokens immediately
        for _ in range(10):
            await limiter.acquire()
        
        # Tokens should be depleted
        assert limiter.tokens < 1
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_when_limit_exceeded(self):
        """Test that rate limiter blocks when limit is exceeded"""
        limiter = TokenBucketRateLimiter(max_requests=2, time_window=1.0)
        
        # Acquire 2 tokens
        await limiter.acquire()
        await limiter.acquire()
        
        # Next acquire should block briefly
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should have waited at least a small amount
        assert elapsed > 0.1


class TestJamaClient:
    """Tests for JamaClient"""
    
    def test_client_initialization(self, jama_client, jama_config):
        """Test that client initializes correctly"""
        assert jama_client.project_id == jama_config.project_id
        assert jama_client.rate_limiter is not None
        assert jama_client.client is not None
    
    @pytest.mark.asyncio
    async def test_get_activities_success(self, jama_client):
        """Test successful activity retrieval"""
        # Mock the py-jama-rest-client response
        mock_activities = [
            {
                'id': 1,
                'activityType': 'ITEM_CREATED',
                'objectId': 100,
                'date': '2026-02-25T10:00:00Z',
                'userName': 'test_user'
            },
            {
                'id': 2,
                'activityType': 'ITEM_UPDATED',
                'objectId': 101,
                'date': '2026-02-25T11:00:00Z',
                'userName': 'test_user'
            }
        ]
        
        jama_client.client.get_activities = Mock(return_value=mock_activities)
        
        since = datetime.now() - timedelta(hours=1)
        activities = await jama_client.get_activities(since)
        
        assert len(activities) == 2
        assert activities[0].activity_type == 'ITEM_CREATED'
        assert activities[0].item_id == 100
        assert activities[1].activity_type == 'ITEM_UPDATED'
        assert activities[1].item_id == 101
    
    @pytest.mark.asyncio
    async def test_get_item_success(self, jama_client):
        """Test successful item retrieval"""
        # Mock the py-jama-rest-client response
        mock_item = {
            'data': {
                'id': 100,
                'project': 12345,
                'itemType': 'Requirement',
                'modifiedDate': '2026-02-25T10:00:00Z',
                'fields': {
                    'name': 'Test Requirement',
                    'description': 'Test description',
                    'status': 'Draft',
                    'priority': 'High'
                }
            }
        }
        
        jama_client.client.get_item = Mock(return_value=mock_item)
        
        item = await jama_client.get_item(100)
        
        assert item.id == 100
        assert item.name == 'Test Requirement'
        assert item.status == 'Draft'
        assert item.priority == 'High'
    
    @pytest.mark.asyncio
    async def test_update_item_success(self, jama_client):
        """Test successful item update"""
        jama_client.client.patch_item = Mock(return_value=None)
        
        fields = {'status': 'Approved', 'priority': 'Medium'}
        await jama_client.update_item(100, fields)
        
        # Verify patch_item was called
        jama_client.client.patch_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_item_rate_limit_retry(self, jama_client):
        """Test that update_item retries on 429 rate limit"""
        # First call raises 429, second succeeds
        jama_client.client.patch_item = Mock(
            side_effect=[
                Exception("429 Rate limit exceeded"),
                None
            ]
        )
        
        fields = {'status': 'Approved'}
        await jama_client.update_item(100, fields)
        
        # Should have been called twice (initial + retry)
        assert jama_client.client.patch_item.call_count == 2
    
    @pytest.mark.asyncio
    async def test_update_item_non_rate_limit_error(self, jama_client):
        """Test that update_item raises non-rate-limit errors immediately"""
        jama_client.client.patch_item = Mock(
            side_effect=Exception("500 Internal Server Error")
        )
        
        fields = {'status': 'Approved'}
        
        with pytest.raises(Exception, match="500 Internal Server Error"):
            await jama_client.update_item(100, fields)
        
        # Should only be called once (no retry for non-429 errors)
        assert jama_client.client.patch_item.call_count == 1
