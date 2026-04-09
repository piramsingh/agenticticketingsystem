"""Azure DevOps connector implementation."""
import asyncio
import base64
import json as _json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseConnector
from ..models.ticket import Activity, CreateItemResult, TargetItem, WebhookEvent

logger = logging.getLogger(__name__)


class AzureDevOpsConnector(BaseConnector):
    """
    Azure DevOps connector.

    Talks to the Azure DevOps REST API (7.0) to create/update/get work items,
    parse service-hook webhooks, list members, and resolve users.
    """

    # Canonical → Azure DevOps priority int (1 = Critical … 4 = Low)
    _PRIORITY_MAP: Dict[str, int] = {
        "critical": 1,
        "high":     2,
        "medium":   3,
        "low":      4,
    }

    # Canonical ticket type → Azure DevOps work item type
    # Mapped to Basic process template types: Issue, Epic, Task
    _TYPE_MAP: Dict[str, str] = {
        "bug":        "Issue",
        "feature":    "Epic",
        "task":       "Task",
        "user story": "Task",
    }

    def __init__(self, base_url: str, pat: str, project: str,
                 work_item_type: str = "Task"):
        self.base_url = base_url.rstrip("/")
        self.pat = pat
        self.project = project
        self.work_item_type = work_item_type
        self.api_version = "7.0"

        auth_string = f":{pat}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json-patch+json",
            },
            timeout=30.0,
        )

    # ── Field normalisation ───────────────────────────────────────────────────

    def normalize_priority(self, canonical: str) -> int:
        """
        Convert canonical priority → Azure DevOps int (1–4).

        Args:
            canonical: One of "critical", "high", "medium", "low" (case-insensitive).

        Returns:
            Integer 1 (Critical) through 4 (Low). Defaults to 3 (Medium).
        """
        return self._PRIORITY_MAP.get(canonical.lower(), 3)

    def normalize_type(self, canonical: str) -> str:
        """
        Convert canonical ticket type → Azure DevOps work item type string.

        Args:
            canonical: One of "Bug", "Feature", "Task", "User Story" (case-insensitive).

        Returns:
            Azure DevOps type string. Defaults to "Task".
        """
        return self._TYPE_MAP.get(canonical.lower(), "Task")

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """Create a work item via the Azure DevOps REST API (JSON Patch format)."""
        work_item_type = fields.pop("type", self.work_item_type)
        url = f"{self.base_url}/{self.project}/_apis/wit/workitems/${work_item_type}"
        params = {"api-version": self.api_version}

        field_mapping = {
            "title":       "System.Title",
            "description": "System.Description",
            "priority":    "Microsoft.VSTS.Common.Priority",
            "tags":        "System.Tags",
            "assignee_id": "System.AssignedTo",
        }

        patch_document = [
            {"op": "add", "path": f"/fields/{ado_field}", "value": field_value}
            for field_key, field_value in fields.items()
            if (ado_field := field_mapping.get(field_key)) and field_value is not None
        ]

        logger.info("Creating Azure DevOps work item in project %s", self.project)

        for attempt, delay in enumerate([1, 2, 4]):
            try:
                response = await self.client.post(
                    url,
                    content=_json.dumps(patch_document),
                    headers={"Content-Type": "application/json-patch+json"},
                    params=params,
                )
                response.raise_for_status()
                result = response.json()
                item_id = str(result["id"])
                item_url = result["_links"]["html"]["href"]
                created_at = datetime.fromisoformat(
                    result["fields"]["System.CreatedDate"].replace("Z", "+00:00")
                )
                logger.info("Created Azure DevOps work item %s", item_id)
                return CreateItemResult(item_id=item_id, item_url=item_url, created_at=created_at)
            except httpx.HTTPError as e:
                if self._categorize_error(e) == "transient" and attempt < 2:
                    logger.warning("Transient error, retrying in %ds: %s", delay, e)
                    await asyncio.sleep(delay)
                    continue
                logger.error("Failed to create work item: %s", e, exc_info=True)
                raise

    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """Update a work item via JSON Patch."""
        url = f"{self.base_url}/{self.project}/_apis/wit/workitems/{item_id}"
        params = {"api-version": self.api_version}

        field_mapping = {
            "title":       "System.Title",
            "description": "System.Description",
            "priority":    "Microsoft.VSTS.Common.Priority",
            "status":      "System.State",
            "state":       "System.State",
        }

        patch_document = [
            {"op": "replace", "path": f"/fields/{field_mapping.get(k, k)}", "value": v}
            for k, v in fields.items()
        ]

        logger.info("Updating Azure DevOps work item %s", item_id)

        for attempt, delay in enumerate([1, 2, 4]):
            try:
                response = await self.client.patch(url, json=patch_document, params=params)
                response.raise_for_status()
                logger.info("Updated Azure DevOps work item %s", item_id)
                return
            except httpx.HTTPError as e:
                if self._categorize_error(e) == "transient" and attempt < 2:
                    await asyncio.sleep(delay)
                    continue
                logger.error("Failed to update work item %s: %s", item_id, e, exc_info=True)
                raise

    async def get_item(self, item_id: str) -> TargetItem:
        """Retrieve a work item from Azure DevOps."""
        url = f"{self.base_url}/{self.project}/_apis/wit/workitems/{item_id}"
        params = {"api-version": self.api_version}

        for attempt, delay in enumerate([1, 2, 4]):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
                f = result["fields"]
                ts_str = f.get("System.ChangedDate") or f.get("System.CreatedDate")
                last_modified = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                return TargetItem(
                    item_id=str(result["id"]),
                    title=f.get("System.Title", ""),
                    description=f.get("System.Description", ""),
                    status=f.get("System.State", ""),
                    priority=str(f.get("Microsoft.VSTS.Common.Priority", "")),
                    last_modified=last_modified,
                    fields=f,
                )
            except httpx.HTTPError as e:
                cat = self._categorize_error(e)
                if cat == "not_found":
                    logger.warning("Work item %s not found", item_id)
                    raise
                if cat == "transient" and attempt < 2:
                    await asyncio.sleep(delay)
                    continue
                logger.error("Failed to get work item %s: %s", item_id, e, exc_info=True)
                raise

    # ── Webhooks ──────────────────────────────────────────────────────────────

    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse an Azure DevOps service-hook payload."""
        try:
            raw_type = payload.get("eventType", "")
            type_map = {
                "workitem.created": "created",
                "workitem.updated": "updated",
                "workitem.deleted": "deleted",
            }
            event_type = type_map.get(raw_type, "updated")

            resource = payload.get("resource", {})
            item_id = str(resource.get("id", ""))
            if not item_id:
                raise ValueError("Missing work item ID in webhook payload")

            fields = resource.get("fields", {})
            updated_fields: Dict[str, Any] = {}
            if "System.Title" in fields:
                updated_fields["title"] = fields["System.Title"]
            if "System.Description" in fields:
                updated_fields["description"] = fields["System.Description"]
            if "System.State" in fields:
                updated_fields["status"] = fields["System.State"]
            if "Microsoft.VSTS.Common.Priority" in fields:
                updated_fields["priority"] = fields["Microsoft.VSTS.Common.Priority"]

            ts_str = (
                fields.get("System.ChangedDate")
                or resource.get("revisedDate")
                or payload.get("createdDate")
            )
            timestamp = (
                datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts_str else datetime.utcnow()
            )

            return WebhookEvent(
                event_type=event_type,
                item_id=item_id,
                updated_fields=updated_fields,
                timestamp=timestamp,
            )
        except (KeyError, ValueError) as e:
            logger.error("Failed to parse Azure DevOps webhook: %s", e)
            raise ValueError(f"Invalid Azure DevOps webhook payload: {e}")

    # ── Connectivity ──────────────────────────────────────────────────────────

    async def validate_connection(self) -> bool:
        """Verify credentials by fetching project info."""
        try:
            url = f"{self.base_url}/_apis/projects/{self.project}"
            response = await self.client.get(url, params={"api-version": self.api_version})
            response.raise_for_status()
            logger.info("Azure DevOps connection validated")
            return True
        except httpx.HTTPError as e:
            logger.error("Azure DevOps connection failed: %s", e)
            return False

    # ── Listing ───────────────────────────────────────────────────────────────

    async def list_items(self, limit: int = 10) -> List[dict]:
        """Return the most recently modified work items as plain dicts."""
        limit = min(limit, 50)
        wiql_url = f"{self.base_url}/{self.project}/_apis/wit/wiql"
        wiql_body = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                "WHERE [System.TeamProject] = @project "
                "ORDER BY [System.ChangedDate] DESC"
            )
        }
        try:
            resp = await self.client.post(
                wiql_url,
                json=wiql_body,
                headers={"Content-Type": "application/json"},
                params={"api-version": self.api_version, "$top": limit},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("WIQL query failed: %s", e)
            return []

        ids = [str(item["id"]) for item in resp.json().get("workItems", [])[:limit]]
        if not ids:
            return []

        fields_param = "System.Id,System.Title,System.State,Microsoft.VSTS.Common.Priority,System.AssignedTo"
        try:
            batch_resp = await self.client.get(
                f"{self.base_url}/{self.project}/_apis/wit/workitems",
                params={"ids": ",".join(ids), "fields": fields_param, "api-version": self.api_version},
            )
            batch_resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Batch work-item fetch failed: %s", e)
            return []

        results = []
        for item in batch_resp.json().get("value", []):
            f = item.get("fields", {})
            assigned_to = f.get("System.AssignedTo", {})
            if isinstance(assigned_to, dict):
                assigned_to = assigned_to.get("displayName", "")
            results.append({
                "id":         str(item["id"]),
                "title":      f.get("System.Title", ""),
                "status":     f.get("System.State", ""),
                "priority":   str(f.get("Microsoft.VSTS.Common.Priority", "")),
                "assignedTo": assigned_to or "Unassigned",
                "url":        f"{self.base_url}/{self.project}/_workitems/edit/{item['id']}",
            })
        return results

    async def list_members(self) -> List[dict]:
        """Return all project team members for @mention autocomplete."""
        members: Dict[str, str] = {}
        try:
            teams_resp = await self.client.get(
                f"{self.base_url}/_apis/projects/{self.project}/teams",
                params={"api-version": self.api_version},
            )
            teams_resp.raise_for_status()
            for team in teams_resp.json().get("value", []):
                members_resp = await self.client.get(
                    f"{self.base_url}/_apis/projects/{self.project}/teams/{team['id']}/members",
                    params={"api-version": self.api_version},
                )
                if not members_resp.is_success:
                    continue
                for m in members_resp.json().get("value", []):
                    identity = m.get("identity", {})
                    display = identity.get("displayName", "")
                    unique = identity.get("uniqueName", "")
                    if display and unique:
                        members[unique] = display
        except Exception as e:
            logger.warning("list_members failed: %s", e)
        return [{"displayName": d, "uniqueName": u} for u, d in members.items()]

    async def resolve_user(self, name: str) -> Optional[str]:
        """Look up a user by display name, return their unique name (email)."""
        name_lower = name.lower()

        # Step 1: search team members
        try:
            teams_resp = await self.client.get(
                f"{self.base_url}/_apis/projects/{self.project}/teams",
                params={"api-version": self.api_version},
            )
            teams_resp.raise_for_status()
            for team in teams_resp.json().get("value", []):
                members_resp = await self.client.get(
                    f"{self.base_url}/_apis/projects/{self.project}/teams/{team['id']}/members",
                    params={"api-version": self.api_version},
                )
                if not members_resp.is_success:
                    continue
                for member in members_resp.json().get("value", []):
                    identity = member.get("identity", {})
                    display = identity.get("displayName", "")
                    unique = identity.get("uniqueName", "")
                    if name_lower in display.lower() or name_lower in unique.lower():
                        logger.info("Resolved '%s' → %s (%s)", name, unique, display)
                        return unique
        except Exception as e:
            logger.warning("Team member lookup failed: %s", e)

        # Step 2: identity search API fallback
        try:
            org = self.base_url.rstrip("/").split("/")[-1]
            resp = await self.client.get(
                f"https://vssps.dev.azure.com/{org}/_apis/identities",
                params={"searchFilter": "General", "filterValue": name, "queryMembership": "None", "api-version": "6.0"},
            )
            if resp.is_success:
                for identity in resp.json().get("value", []):
                    display = identity.get("providerDisplayName", "")
                    unique = identity.get("properties", {}).get("Account", {}).get("$value", "")
                    if name_lower in display.lower() and unique:
                        logger.info("Resolved '%s' via identity search → %s", name, unique)
                        return unique
        except Exception as e:
            logger.warning("Identity search failed: %s", e)

        logger.warning("Could not resolve user '%s' in project '%s'", name, self.project)
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _categorize_error(self, error: Exception) -> str:
        """Classify an httpx error for retry/logging decisions."""
        if isinstance(error, httpx.HTTPError) and hasattr(error, "response") and error.response is not None:
            code = error.response.status_code
            if code == 429:          return "rate_limit"
            if code in (401, 403):   return "authentication"
            if code == 404:          return "not_found"
            if code == 400:          return "validation"
            if code == 500:          return "server"
            if code in (502, 503, 504): return "transient"
        s = str(error).lower()
        if "429" in s or "rate limit" in s:    return "rate_limit"
        if "401" in s or "403" in s:           return "authentication"
        if "404" in s or "not found" in s:     return "not_found"
        if "400" in s or "bad request" in s:   return "validation"
        if "500" in s:                         return "server"
        if "timeout" in s or "connection" in s: return "transient"
        return "unknown"
