"""Azure DevOps connector implementation"""
import asyncio
import base64
import json as _json
import logging
from datetime import datetime
from typing import Dict, Any
import httpx

from .base import BaseConnector
from ...models.data_models import CreateItemResult, TargetItem, WebhookEvent

logger = logging.getLogger(__name__)


class AzureDevOpsConnector(BaseConnector):
    """
    Azure DevOps Server connector implementation.
    
    This connector integrates with Azure DevOps REST API to create, update,
    and retrieve work items, as well as parse webhook events.
    """
    
    def __init__(self, base_url: str, pat: str, project: str, work_item_type: str = "User Story"):
        """
        Initialize Azure DevOps connector.
        
        Args:
            base_url: Azure DevOps organization URL (e.g., https://dev.azure.com/org)
            pat: Personal Access Token for authentication
            project: Project name or ID
            work_item_type: Default work item type to create (default: "User Story")
        """
        self.base_url = base_url.rstrip('/')
        self.pat = pat
        self.project = project
        self.work_item_type = work_item_type
        self.api_version = "7.0"
        
        # Create HTTP client with authentication
        auth_string = f":{pat}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json-patch+json"
            },
            timeout=30.0
        )
    
    def _encode_pat(self) -> str:
        """Encode PAT for Basic authentication."""
        auth_string = f":{self.pat}"
        return base64.b64encode(auth_string.encode()).decode()
    
    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """
        Create a work item in Azure DevOps.
        
        Uses the Azure DevOps REST API to create a work item with the specified fields.
        The API expects a JSON Patch document format.
        
        Args:
            fields: Dictionary of field values. Expected keys:
                   - title: Work item title (required)
                   - description: Work item description
                   - priority: Priority value
                   - state: Work item state
        
        Returns:
            CreateItemResult with item ID, URL, and creation timestamp.
        
        Raises:
            httpx.HTTPError: If API request fails after retries.
        """
        url = f"{self.base_url}/{self.project}/_apis/wit/workitems/${self.work_item_type}"
        params = {"api-version": self.api_version}
        
        # Build JSON Patch document
        patch_document = []
        
        # Map fields to Azure DevOps field names
        field_mapping = {
            "title":       "System.Title",
            "description": "System.Description",
            "priority":    "Microsoft.VSTS.Common.Priority",
            "tags":        "System.Tags",
            "assignedTo":  "System.AssignedTo",
        }

        for field_key, field_value in fields.items():
            ado_field = field_mapping.get(field_key)
            if not ado_field:
                continue  # skip unmapped fields (e.g. state, assignedTo) to avoid 400s
            patch_document.append({
                "op": "add",
                "path": f"/fields/{ado_field}",
                "value": field_value
            })
        
        logger.info(f"Creating Azure DevOps work item in project {self.project}")
        logger.debug(f"Patch document: {patch_document}")
        
        # Retry with exponential backoff for transient errors
        max_retries = 3
        backoff_delays = [1, 2, 4]  # seconds
        
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    url,
                    content=_json.dumps(patch_document),
                    headers={"Content-Type": "application/json-patch+json"},
                    params=params
                )
                response.raise_for_status()
                
                result = response.json()
                item_id = str(result["id"])
                item_url = result["_links"]["html"]["href"]
                created_at = datetime.fromisoformat(result["fields"]["System.CreatedDate"].replace("Z", "+00:00"))
                
                logger.info(f"Created Azure DevOps work item {item_id}")
                
                return CreateItemResult(
                    item_id=item_id,
                    item_url=item_url,
                    created_at=created_at
                )
            except httpx.HTTPError as e:
                error_category = self._categorize_error(e)
                
                # Retry on transient errors
                if error_category == 'transient' and attempt < max_retries - 1:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        f"Transient error creating work item, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                
                # Log error with full context
                logger.error(
                    f"Failed to create Azure DevOps work item (category: {error_category}): {e}",
                    exc_info=True
                )
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
                raise
    
    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """
        Update a work item in Azure DevOps.
        
        Uses PATCH with JSON Patch format to update work item fields.
        
        Args:
            item_id: ID of the work item to update.
            fields: Dictionary of field values to update.
        
        Raises:
            httpx.HTTPError: If API request fails after retries.
        """
        url = f"{self.base_url}/{self.project}/_apis/wit/workitems/{item_id}"
        params = {"api-version": self.api_version}
        
        # Build JSON Patch document
        patch_document = []
        
        # Map fields to Azure DevOps field names
        field_mapping = {
            "title": "System.Title",
            "description": "System.Description",
            "priority": "Microsoft.VSTS.Common.Priority",
            "state": "System.State"
        }
        
        for field_key, field_value in fields.items():
            ado_field = field_mapping.get(field_key, field_key)
            patch_document.append({
                "op": "replace",
                "path": f"/fields/{ado_field}",
                "value": field_value
            })
        
        logger.info(f"Updating Azure DevOps work item {item_id}")
        logger.debug(f"Patch document: {patch_document}")
        
        # Retry with exponential backoff for transient errors
        max_retries = 3
        backoff_delays = [1, 2, 4]  # seconds
        
        for attempt in range(max_retries):
            try:
                response = await self.client.patch(url, json=patch_document, params=params)
                response.raise_for_status()
                
                logger.info(f"Updated Azure DevOps work item {item_id}")
                return
            except httpx.HTTPError as e:
                error_category = self._categorize_error(e)
                
                # Retry on transient errors
                if error_category == 'transient' and attempt < max_retries - 1:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        f"Transient error updating work item {item_id}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                
                # Log error with full context
                logger.error(
                    f"Failed to update Azure DevOps work item {item_id} (category: {error_category}): {e}",
                    exc_info=True
                )
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
                raise
    
    async def get_item(self, item_id: str) -> TargetItem:
        """
        Retrieve work item details from Azure DevOps.
        
        Args:
            item_id: ID of the work item to retrieve.
        
        Returns:
            TargetItem with the work item's current state.
        
        Raises:
            httpx.HTTPError: If API request fails after retries or item not found.
        """
        url = f"{self.base_url}/{self.project}/_apis/wit/workitems/{item_id}"
        params = {"api-version": self.api_version}
        
        logger.info(f"Retrieving Azure DevOps work item {item_id}")
        
        # Retry with exponential backoff for transient errors
        max_retries = 3
        backoff_delays = [1, 2, 4]  # seconds
        
        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                
                result = response.json()
                fields = result["fields"]
                
                # Parse last modified timestamp
                last_modified_str = fields.get("System.ChangedDate", fields.get("System.CreatedDate"))
                last_modified = datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
                
                target_item = TargetItem(
                    item_id=str(result["id"]),
                    title=fields.get("System.Title", ""),
                    description=fields.get("System.Description", ""),
                    status=fields.get("System.State", ""),
                    priority=str(fields.get("Microsoft.VSTS.Common.Priority", "")),
                    last_modified=last_modified,
                    fields=fields
                )
                
                logger.info(f"Retrieved Azure DevOps work item {item_id}")
                return target_item
            except httpx.HTTPError as e:
                error_category = self._categorize_error(e)
                
                # Don't retry on not_found errors
                if error_category == 'not_found':
                    logger.warning(f"Azure DevOps work item {item_id} not found")
                    raise
                
                # Retry on transient errors
                if error_category == 'transient' and attempt < max_retries - 1:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        f"Transient error retrieving work item {item_id}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                
                # Log error with full context
                logger.error(
                    f"Failed to retrieve Azure DevOps work item {item_id} (category: {error_category}): {e}",
                    exc_info=True
                )
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
                raise
    
    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Parse Azure DevOps service hook webhook payload.
        
        Handles workitem.updated and workitem.created event types.
        
        Args:
            payload: Raw webhook payload from Azure DevOps.
        
        Returns:
            WebhookEvent with standardized event data.
        
        Raises:
            ValueError: If payload format is invalid.
        """
        try:
            event_type_raw = payload.get("eventType", "")
            
            # Map Azure DevOps event types to standardized types
            if event_type_raw == "workitem.created":
                event_type = "created"
            elif event_type_raw == "workitem.updated":
                event_type = "updated"
            elif event_type_raw == "workitem.deleted":
                event_type = "deleted"
            else:
                logger.warning(f"Unknown Azure DevOps event type: {event_type_raw}")
                event_type = "updated"  # Default to updated
            
            # Extract work item details from resource
            resource = payload.get("resource", {})
            item_id = str(resource.get("id", ""))
            
            if not item_id:
                raise ValueError("Missing work item ID in webhook payload")
            
            # Extract updated fields
            fields = resource.get("fields", {})
            updated_fields = {}
            
            # Map Azure DevOps fields to standardized names
            if "System.Title" in fields:
                updated_fields["title"] = fields["System.Title"]
            if "System.Description" in fields:
                updated_fields["description"] = fields["System.Description"]
            if "System.State" in fields:
                updated_fields["state"] = fields["System.State"]
            if "Microsoft.VSTS.Common.Priority" in fields:
                updated_fields["priority"] = fields["Microsoft.VSTS.Common.Priority"]
            
            # Parse timestamp
            timestamp_str = resource.get("fields", {}).get("System.ChangedDate") or \
                          resource.get("revisedDate") or \
                          payload.get("createdDate")
            
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.utcnow()
            
            logger.info(f"Parsed Azure DevOps webhook: {event_type} for item {item_id}")
            
            return WebhookEvent(
                event_type=event_type,
                item_id=item_id,
                updated_fields=updated_fields,
                timestamp=timestamp
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse Azure DevOps webhook: {e}")
            logger.debug(f"Payload: {payload}")
            raise ValueError(f"Invalid Azure DevOps webhook payload: {e}")
    
    async def validate_connection(self) -> bool:
        """
        Test connectivity to Azure DevOps API.
        
        Attempts to retrieve project information to verify authentication and connectivity.
        
        Returns:
            True if connection is successful, False otherwise.
        """
        url = f"{self.base_url}/_apis/projects/{self.project}"
        params = {"api-version": self.api_version}
        
        logger.info(f"Validating Azure DevOps connection to project {self.project}")
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            logger.info("Azure DevOps connection validated successfully")
            return True
        except httpx.HTTPError as e:
            error_category = self._categorize_error(e)
            logger.error(
                f"Azure DevOps connection validation failed (category: {error_category}): {e}",
                exc_info=True
            )
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
            return False
    
    def _categorize_error(self, error: Exception) -> str:
        """
        Categorize error for better logging and retry logic.
        
        Error categories:
        - transient: Network errors, timeouts, 502/503 (should retry)
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
        
        # Check HTTP status code if available
        if isinstance(error, httpx.HTTPError) and hasattr(error, 'response') and error.response is not None:
            status_code = error.response.status_code
            
            if status_code == 429:
                return 'rate_limit'
            elif status_code in (401, 403):
                return 'authentication'
            elif status_code == 404:
                return 'not_found'
            elif status_code == 400:
                return 'validation'
            elif status_code == 500:
                return 'server'
            elif status_code in (502, 503, 504):
                return 'transient'
        
        # Fallback to string matching
        if '429' in error_str or 'rate limit' in error_str:
            return 'rate_limit'
        elif '401' in error_str or '403' in error_str or 'unauthorized' in error_str or 'forbidden' in error_str:
            return 'authentication'
        elif '404' in error_str or 'not found' in error_str:
            return 'not_found'
        elif '400' in error_str or 'bad request' in error_str or 'validation' in error_str:
            return 'validation'
        elif '500' in error_str or 'server error' in error_str:
            return 'server'
        elif 'timeout' in error_str or 'connection' in error_str or 'network' in error_str:
            return 'transient'
        
        # Unknown error
        return 'unknown'
    
    async def resolve_user(self, name: str) -> str | None:
        """
        Look up an Azure DevOps user by display name or partial name.

        Searches project team members first, then falls back to the
        identity search API. Returns the user's unique name (email)
        suitable for use with System.AssignedTo, or None if not found.

        Args:
            name: Display name or first name to search for (case-insensitive)

        Returns:
            Unique name (email) string, or None if no match found
        """
        name_lower = name.lower()

        # Step 1 — search project teams for a matching member
        try:
            teams_url = f"{self.base_url}/_apis/projects/{self.project}/teams"
            teams_resp = await self.client.get(teams_url, params={"api-version": self.api_version})
            teams_resp.raise_for_status()
            teams = teams_resp.json().get("value", [])

            for team in teams:
                members_url = (
                    f"{self.base_url}/_apis/projects/{self.project}"
                    f"/teams/{team['id']}/members"
                )
                members_resp = await self.client.get(
                    members_url, params={"api-version": self.api_version}
                )
                if not members_resp.is_success:
                    continue
                for member in members_resp.json().get("value", []):
                    identity = member.get("identity", {})
                    display = identity.get("displayName", "")
                    unique  = identity.get("uniqueName", "")
                    if name_lower in display.lower():
                        logger.info(f"Resolved '{name}' → {unique} ({display})")
                        return unique
        except Exception as e:
            logger.warning(f"Team member lookup failed: {e}")

        # Step 2 — fall back to identity search API (vssps subdomain)
        try:
            org = self.base_url.rstrip("/").split("/")[-1]
            search_url = (
                f"https://vssps.dev.azure.com/{org}/_apis/identities"
            )
            resp = await self.client.get(
                search_url,
                params={
                    "searchFilter": "General",
                    "filterValue": name,
                    "queryMembership": "None",
                    "api-version": "6.0",
                },
            )
            if resp.is_success:
                for identity in resp.json().get("value", []):
                    display = identity.get("providerDisplayName", "")
                    unique  = identity.get("properties", {}).get("Account", {}).get("$value", "")
                    if name_lower in display.lower() and unique:
                        logger.info(f"Resolved '{name}' via identity search → {unique}")
                        return unique
        except Exception as e:
            logger.warning(f"Identity search failed: {e}")

        logger.warning(f"Could not resolve user '{name}' in project '{self.project}'")
        return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
