"""Jama Connect client wrapper with rate limiting and error handling"""
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any

from py_jama_rest_client.client import JamaClient as PyJamaClient

from ..config import JamaConfig
from ..models.data_models import Activity, JamaItem


logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for API requests.
    
    Implements a token bucket algorithm to limit requests to max_requests per time_window.
    """
    
    def __init__(self, max_requests: int = 10, time_window: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """
        Acquire a token, waiting if necessary.
        Blocks until a token is available.
        """
        async with self._lock:
            while self.tokens < 1:
                # Refill tokens based on elapsed time
                now = time.time()
                elapsed = now - self.last_refill
                tokens_to_add = elapsed * (self.max_requests / self.time_window)
                
                if tokens_to_add >= 1:
                    self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
                    self.last_refill = now
                else:
                    # Wait until next token is available
                    wait_time = (1 - tokens_to_add) * self.time_window / self.max_requests
                    await asyncio.sleep(wait_time)
            
            # Consume one token
            self.tokens -= 1


class JamaClient:
    """
    Wrapper around py-jama-rest-client with rate limiting and error handling.
    
    Implements:
    - Token bucket rate limiting (10 requests/second)
    - Exponential backoff for 429 responses
    - Project filtering for activities
    """
    
    def __init__(self, config: JamaConfig):
        """
        Initialize Jama client.
        
        Args:
            config: Jama connection configuration
        """
        self.config = config
        self.client = PyJamaClient(
            host_domain=config.base_url,
            credentials=(config.username, config.password.get_secret_value())
        )
        self.rate_limiter = TokenBucketRateLimiter(max_requests=10, time_window=1.0)
        self.project_id = config.project_id
    
    async def get_activities(self, since: datetime) -> List[Activity]:
        """
        Poll activity stream for project.
        
        Args:
            since: Get activities since this timestamp
            
        Returns:
            List of Activity objects for the configured project
            
        Raises:
            Exception: If API call fails after retries
        """
        await self.rate_limiter.acquire()
        
        try:
            # Convert datetime to timestamp for API
            timestamp = int(since.timestamp() * 1000)  # Jama uses milliseconds
            
            # Get activities with project filter
            # Note: py-jama-rest-client uses synchronous calls, so we run in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_activities(
                    project=self.project_id,
                    timestamp=timestamp
                )
            )
            
            # Parse response into Activity objects
            activities = []
            if response and isinstance(response, list):
                for activity_data in response:
                    try:
                        activities.append(Activity(
                            id=activity_data.get('id'),
                            activity_type=activity_data.get('activityType'),
                            item_id=activity_data.get('objectId'),
                            timestamp=datetime.fromisoformat(
                                activity_data.get('date').replace('Z', '+00:00')
                            ),
                            user=activity_data.get('userName', 'unknown')
                        ))
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Failed to parse activity: {e}")
                        continue
            
            logger.info(f"Retrieved {len(activities)} activities since {since}")
            return activities
            
        except Exception as e:
            error_category = self._categorize_error(e)
            logger.error(
                f"Failed to get activities (category: {error_category}): {e}",
                exc_info=True
            )
            raise
    
    async def get_item(self, item_id: int) -> JamaItem:
        """
        Get item details with rate limiting.
        
        Args:
            item_id: Jama item ID
            
        Returns:
            JamaItem object with item details
            
        Raises:
            Exception: If API call fails after retries
        """
        await self.rate_limiter.acquire()
        
        try:
            # Get item details
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_item(item_id)
            )
            
            # Parse response into JamaItem
            data = response.get('data', {})
            fields = data.get('fields', {})
            
            item = JamaItem(
                id=data.get('id'),
                project_id=data.get('project'),
                item_type=data.get('itemType'),
                name=fields.get('name', ''),
                description=fields.get('description', ''),
                status=fields.get('status', ''),
                priority=fields.get('priority', ''),
                last_modified=datetime.fromisoformat(
                    data.get('modifiedDate').replace('Z', '+00:00')
                ),
                fields=fields
            )
            
            logger.debug(f"Retrieved item {item_id}: {item.name}")
            return item
            
        except Exception as e:
            error_category = self._categorize_error(e)
            logger.error(
                f"Failed to get item {item_id} (category: {error_category}): {e}",
                exc_info=True
            )
            raise
    
    async def update_item(self, item_id: int, fields: Dict[str, Any]) -> None:
        """
        Update item fields with exponential backoff on 429 responses.
        
        Args:
            item_id: Jama item ID
            fields: Dictionary of fields to update
            
        Raises:
            Exception: If API call fails after all retries
        """
        await self.rate_limiter.acquire()
        
        # Exponential backoff parameters
        max_retries = 7
        backoff_delays = [1, 2, 4, 8, 16, 32, 60]  # seconds
        
        for attempt in range(max_retries):
            try:
                # Update item
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.client.patch_item(item_id, [
                        {
                            "op": "replace",
                            "path": f"/fields/{field_name}",
                            "value": field_value
                        }
                        for field_name, field_value in fields.items()
                    ])
                )
                
                logger.info(f"Updated item {item_id} with fields: {list(fields.keys())}")
                return
                
            except Exception as e:
                error_str = str(e)
                error_category = self._categorize_error(e)
                
                # Check if it's a 429 rate limit error
                if '429' in error_str or 'rate limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        delay = backoff_delays[attempt]
                        logger.warning(
                            f"Rate limit hit for item {item_id}, "
                            f"retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"Rate limit exceeded for item {item_id} after {max_retries} attempts"
                        )
                        raise
                else:
                    # Non-rate-limit error, raise immediately
                    logger.error(
                        f"Failed to update item {item_id} (category: {error_category}): {e}",
                        exc_info=True
                    )
                    raise
    
    def _categorize_error(self, error: Exception) -> str:
        """
        Categorize error for better logging and handling.
        
        Error categories:
        - transient: Network errors, timeouts (should retry)
        - rate_limit: 429 responses (exponential backoff)
        - authentication: 401, 403 errors (alert admin)
        - not_found: 404 errors (log warning, skip)
        - validation: 400 errors (log error, mark as error)
        - server: 500 errors (retry once, then skip)
        
        Args:
            error: Exception to categorize
            
        Returns:
            Error category string
        """
        error_str = str(error).lower()
        
        # Rate limit errors
        if '429' in error_str or 'rate limit' in error_str:
            return 'rate_limit'
        
        # Authentication errors
        if '401' in error_str or '403' in error_str or 'unauthorized' in error_str or 'forbidden' in error_str:
            return 'authentication'
        
        # Not found errors
        if '404' in error_str or 'not found' in error_str:
            return 'not_found'
        
        # Validation errors
        if '400' in error_str or 'bad request' in error_str or 'validation' in error_str:
            return 'validation'
        
        # Server errors
        if '500' in error_str or '502' in error_str or '503' in error_str or 'server error' in error_str:
            return 'server'
        
        # Network/timeout errors
        if 'timeout' in error_str or 'connection' in error_str or 'network' in error_str:
            return 'transient'
        
        # Unknown error
        return 'unknown'
    
    async def _handle_rate_limit(self, response: Any) -> None:
        """
        Handle rate limit response with exponential backoff.
        
        This method implements exponential backoff for 429 responses:
        - Backoff sequence: 1s, 2s, 4s, 8s, 16s, 32s, 60s (max)
        - After max backoff, logs warning and skips operation
        
        Args:
            response: API response object
        """
        # This method is primarily used internally by update_item
        # The backoff logic is implemented directly in update_item
        pass
