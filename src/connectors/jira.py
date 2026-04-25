"""
Jira Cloud REST API v3 connector.

Auth:   Basic base64(email:api_token)
Base:   https://<domain>.atlassian.net/rest/api/3/
Status: transition-based (cannot set directly)
Desc:   Atlassian Document Format (ADF)
"""
import asyncio
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseConnector
from ..models.ticket import Activity, CreateItemResult, TargetItem, WebhookEvent

logger = logging.getLogger(__name__)


class JiraConnector(BaseConnector):
    """
    Jira Cloud connector (REST API v3).

    Supports: create, update, get, webhook parsing, user search, item listing.
    Status updates go through the Jira transitions API (not a direct field write).
    Descriptions are sent in Atlassian Document Format (ADF).
    """

    # Canonical → Jira priority object
    _PRIORITY_MAP: Dict[str, Dict[str, str]] = {
        "critical": {"name": "Highest"},
        "high":     {"name": "High"},
        "medium":   {"name": "Medium"},
        "low":      {"name": "Low"},
    }

    # Canonical ticket type → Jira issue type name
    _TYPE_MAP: Dict[str, str] = {
        "bug":        "Bug",
        "feature":    "Story",
        "task":       "Task",
        "user story": "Story",
    }

    def __init__(self, base_url: str, email: str, api_token: str, project: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.project = project
        self._valid_issue_types: Optional[List[str]] = None  # fetched lazily
        self._active_sprint_id: Optional[int] = None         # fetched lazily

        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._api     = f"{self.base_url}/rest/api/3"
        self._agile   = f"{self.base_url}/rest/agile/1.0"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Basic {credentials}",
                "Accept":        "application/json",
                "Content-Type":  "application/json",
            },
            timeout=30.0,
            follow_redirects=False,
        )

    # ── Field normalisation ───────────────────────────────────────────────────

    def normalize_priority(self, canonical: str) -> Dict[str, str]:
        """
        Convert canonical priority → Jira priority object.

        Args:
            canonical: "critical" | "high" | "medium" | "low"

        Returns:
            Dict like {"name": "High"} that Jira's API expects.
        """
        return self._PRIORITY_MAP.get(canonical.lower(), {"name": "Medium"})

    def normalize_type(self, canonical: str) -> str:
        """
        Convert canonical ticket type → Jira issue type name.

        Pass-through for inputs that aren't in the canonical map — this lets
        the parser's smart picks (e.g. "Epic", "Subtask") survive. The
        connector's _resolve_issue_type validates against real valid types
        before sending the request to Jira.
        """
        return self._TYPE_MAP.get(canonical.lower(), canonical)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """Create a Jira issue via POST /issue."""
        issue_type = fields.pop("type", "Task")
        priority = fields.get("priority", {"name": "Medium"})

        issue_type = await self._resolve_issue_type(issue_type)

        body: Dict[str, Any] = {
            "fields": {
                "project":   {"key": self.project},
                "summary":   fields.get("title", "Untitled"),
                "issuetype": {"name": issue_type},
                "priority":  priority if isinstance(priority, dict) else {"name": str(priority)},
            }
        }

        description = fields.get("description", "")
        if description:
            body["fields"]["description"] = self._to_adf(description)

        if "assignee_id" in fields and fields["assignee_id"]:
            body["fields"]["assignee"] = {"accountId": fields["assignee_id"]}

        if "tags" in fields and fields["tags"]:
            body["fields"]["labels"] = [t.strip() for t in str(fields["tags"]).split(",") if t.strip()]

        logger.info("Creating Jira issue in project %s (type=%s)", self.project, issue_type)

        for attempt, delay in enumerate([1, 2, 4]):
            try:
                resp = await self.client.post(f"{self._api}/issue", json=body)
                if resp.status_code == 400:
                    logger.error("Jira 400 — request body: %s", body)
                    logger.error("Jira 400 — response body: %s", resp.text)
                    if "priority" in body.get("fields", {}):
                        logger.warning("Retrying without priority field")
                        body["fields"].pop("priority", None)
                        resp = await self.client.post(f"{self._api}/issue", json=body)
                        if resp.status_code == 400:
                            logger.error("Still 400 after removing priority — response: %s", resp.text)
                resp.raise_for_status()
                data = resp.json()
                issue_key = data["key"]
                issue_url = f"{self.base_url}/browse/{issue_key}"
                created_at = datetime.utcnow()
                logger.info("Created Jira issue %s", issue_key)

                # Move into the active sprint (best-effort — if it fails the
                # issue still exists in the backlog and we log the reason)
                sprint_id = await self._get_active_sprint_id()
                if sprint_id:
                    await self._assign_to_sprint(issue_key, sprint_id)

                return CreateItemResult(item_id=issue_key, item_url=issue_url, created_at=created_at)
            except httpx.HTTPStatusError as e:
                if self._is_transient(e) and attempt < 2:
                    logger.warning("Transient error, retrying in %ds: %s", delay, e)
                    await asyncio.sleep(delay)
                    continue
                jira_detail = e.response.text if e.response is not None else ""
                logger.error("Failed to create Jira issue: %s — %s", e, jira_detail)
                raise RuntimeError(f"Jira rejected the request: {jira_detail}") from e
            except httpx.HTTPError as e:
                if self._is_transient(e) and attempt < 2:
                    await asyncio.sleep(delay)
                    continue
                logger.error("Failed to create Jira issue: %s", e, exc_info=True)
                raise

    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """
        Update a Jira issue.

        Status changes go through the transitions API; all other fields are
        sent as a direct PUT /issue/{key} body.
        """
        # Handle status separately via transitions
        new_status = fields.pop("status", None) or fields.pop("state", None)
        if new_status:
            await self._apply_transition(item_id, new_status)

        if not fields:
            return

        update_body: Dict[str, Any] = {"fields": {}}

        if "title" in fields:
            update_body["fields"]["summary"] = fields["title"]
        if "description" in fields:
            update_body["fields"]["description"] = self._to_adf(fields["description"])
        if "priority" in fields:
            p = fields["priority"]
            update_body["fields"]["priority"] = p if isinstance(p, dict) else {"name": str(p)}
        if "assignee_id" in fields:
            update_body["fields"]["assignee"] = {"accountId": fields["assignee_id"]}

        for attempt, delay in enumerate([1, 2, 4]):
            try:
                resp = await self.client.put(f"{self._api}/issue/{item_id}", json=update_body)
                resp.raise_for_status()
                logger.info("Updated Jira issue %s", item_id)
                return
            except httpx.HTTPError as e:
                if self._is_transient(e) and attempt < 2:
                    await asyncio.sleep(delay)
                    continue
                logger.error("Failed to update Jira issue %s: %s", item_id, e, exc_info=True)
                raise

    async def get_item(self, item_id: str) -> TargetItem:
        """Retrieve a Jira issue by key or ID."""
        for attempt, delay in enumerate([1, 2, 4]):
            try:
                resp = await self.client.get(f"{self._api}/issue/{item_id}")
                resp.raise_for_status()
                data = resp.json()
                f = data.get("fields", {})

                updated_str = f.get("updated") or f.get("created")
                last_modified = (
                    datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    if updated_str else datetime.utcnow()
                )

                priority_obj = f.get("priority") or {}
                priority = priority_obj.get("name", "") if isinstance(priority_obj, dict) else str(priority_obj)

                description = self._from_adf(f.get("description")) or ""

                return TargetItem(
                    item_id=data["key"],
                    title=f.get("summary", ""),
                    description=description,
                    status=f.get("status", {}).get("name", ""),
                    priority=priority,
                    last_modified=last_modified,
                    fields=f,
                )
            except httpx.HTTPError as e:
                if hasattr(e, "response") and e.response is not None and e.response.status_code == 404:
                    logger.warning("Jira issue %s not found", item_id)
                    raise
                if self._is_transient(e) and attempt < 2:
                    await asyncio.sleep(delay)
                    continue
                logger.error("Failed to get Jira issue %s: %s", item_id, e, exc_info=True)
                raise

    # ── Webhooks ──────────────────────────────────────────────────────────────

    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse a Jira webhook payload into a standardised WebhookEvent."""
        try:
            raw_event = payload.get("webhookEvent", "")
            type_map = {
                "jira:issue_created": "created",
                "jira:issue_updated": "updated",
                "jira:issue_deleted": "deleted",
            }
            event_type = type_map.get(raw_event, "updated")

            issue = payload.get("issue", {})
            item_id = issue.get("key") or str(issue.get("id", ""))
            if not item_id:
                raise ValueError("Missing issue key in webhook payload")

            f = issue.get("fields", {})
            changelog = payload.get("changelog", {})
            updated_fields: Dict[str, Any] = {}

            # Prefer changelog items for fine-grained field tracking
            for change in changelog.get("items", []):
                field = change.get("field", "").lower()
                if field == "summary":
                    updated_fields["title"] = change.get("toString", "")
                elif field == "status":
                    updated_fields["status"] = change.get("toString", "")
                elif field == "priority":
                    updated_fields["priority"] = change.get("toString", "")
                elif field == "description":
                    updated_fields["description"] = change.get("toString", "")

            # Fallback: populate from full fields when changelog is absent
            if not updated_fields:
                if "summary" in f:
                    updated_fields["title"] = f["summary"]
                if "status" in f:
                    updated_fields["status"] = f["status"].get("name", "")

            ts_str = payload.get("timestamp")
            timestamp = (
                datetime.fromtimestamp(ts_str / 1000) if isinstance(ts_str, (int, float))
                else datetime.utcnow()
            )

            return WebhookEvent(
                event_type=event_type,
                item_id=item_id,
                updated_fields=updated_fields,
                timestamp=timestamp,
            )
        except (KeyError, ValueError) as e:
            logger.error("Failed to parse Jira webhook: %s", e)
            raise ValueError(f"Invalid Jira webhook payload: {e}")

    # ── Connectivity ──────────────────────────────────────────────────────────

    async def _fetch_issue_types(self) -> List[str]:
        """Fetch valid issue type names for this project via createmeta."""
        if self._valid_issue_types is not None:
            return self._valid_issue_types
        try:
            resp = await self.client.get(
                f"{self._api}/issue/createmeta",
                params={"projectKeys": self.project, "expand": "projects.issuetypes"},
            )
            resp.raise_for_status()
            projects = resp.json().get("projects", [])
            if projects:
                names = [it["name"] for it in projects[0].get("issuetypes", [])]
                self._valid_issue_types = names
                logger.info("Valid issue types for %s: %s", self.project, names)
                return names
        except httpx.HTTPError as e:
            logger.warning("Could not fetch issue types: %s", e)
        return []

    async def _resolve_issue_type(self, requested: str) -> str:
        """Return *requested* if valid for this project, else the best available fallback."""
        valid = await self._fetch_issue_types()
        if not valid or requested in valid:
            return requested
        # prefer Task → Story → first available
        for fallback in ("Task", "Story", valid[0]):
            if fallback in valid:
                logger.warning(
                    "Issue type '%s' not in project %s %s — using '%s'",
                    requested, self.project, valid, fallback,
                )
                return fallback
        return requested

    async def _assign_to_sprint(self, issue_key: str, sprint_id: int) -> bool:
        """Move an existing issue into the given sprint via the Agile API."""
        try:
            resp = await self.client.post(
                f"{self._agile}/sprint/{sprint_id}/issue",
                json={"issues": [issue_key]},
            )
            resp.raise_for_status()
            logger.info("Moved %s into sprint %d", issue_key, sprint_id)
            return True
        except httpx.HTTPError as e:
            body = getattr(e, "response", None)
            detail = body.text if body is not None else str(e)
            logger.warning("Could not move %s into sprint %d: %s", issue_key, sprint_id, detail)
            return False

    async def _get_active_sprint_id(self) -> Optional[int]:
        """Return the ID of the active sprint for this project, cached after first fetch."""
        if self._active_sprint_id is not None:
            return self._active_sprint_id
        try:
            # Find any board for this project (no type filter — team-managed boards
            # are type 'simple', company-managed are 'scrum'; we want either)
            boards_resp = await self.client.get(
                f"{self._agile}/board",
                params={"projectKeyOrId": self.project},
            )
            boards_resp.raise_for_status()
            boards = boards_resp.json().get("values", [])
            if not boards:
                logger.warning("No board found for project %s", self.project)
                return None

            # Try each board until we find an active sprint
            for board in boards:
                board_id = board["id"]
                board_type = board.get("type", "?")
                try:
                    sprints_resp = await self.client.get(
                        f"{self._agile}/board/{board_id}/sprint",
                        params={"state": "active"},
                    )
                    sprints_resp.raise_for_status()
                    sprints = sprints_resp.json().get("values", [])
                    if sprints:
                        sprint_id = sprints[0]["id"]
                        sprint_name = sprints[0].get("name", sprint_id)
                        logger.info(
                            "Active sprint for %s: %s (id=%d, board=%d type=%s)",
                            self.project, sprint_name, sprint_id, board_id, board_type,
                        )
                        self._active_sprint_id = sprint_id
                        return sprint_id
                except httpx.HTTPError as e:
                    logger.debug("Board %d sprint fetch failed: %s", board_id, e)
                    continue

            logger.warning("No active sprint found across %d boards for %s", len(boards), self.project)
            return None
        except httpx.HTTPError as e:
            logger.warning("Could not fetch active sprint: %s", e)
            return None

    async def get_valid_types(self) -> List[str]:
        return await self._fetch_issue_types()

    async def validate_connection(self) -> bool:
        """Verify credentials and warm up the issue-type cache."""
        try:
            types = await self._fetch_issue_types()
            if types:
                logger.info("Jira connection validated for project %s", self.project)
                return True
            # createmeta returned no types — fall back to a lightweight user check
            resp = await self.client.get(f"{self._api}/myself")
            resp.raise_for_status()
            logger.info("Jira connection validated (myself endpoint) for project %s", self.project)
            return True
        except httpx.HTTPError as e:
            logger.error("Jira connection validation failed: %s", e)
            return False

    # ── Listing ───────────────────────────────────────────────────────────────

    async def list_items(self, limit: int = 10) -> List[dict]:
        """Return recent issues via JQL, sorted by updated date."""
        limit = min(limit, 50)
        jql = f"project = {self.project} ORDER BY updated DESC"
        try:
            resp = await self.client.post(
                f"{self._api}/search/jql",
                json={"jql": jql, "maxResults": limit,
                      "fields": ["summary", "status", "priority", "assignee"]},
            )
            resp.raise_for_status()
            results = []
            for issue in resp.json().get("issues", []):
                f = issue.get("fields", {})
                assignee = f.get("assignee") or {}
                priority = f.get("priority") or {}
                results.append({
                    "id":         issue["key"],
                    "title":      f.get("summary", ""),
                    "status":     f.get("status", {}).get("name", ""),
                    "priority":   priority.get("name", "") if isinstance(priority, dict) else "",
                    "assignedTo": assignee.get("displayName", "Unassigned") if assignee else "Unassigned",
                    "url":        f"{self.base_url}/browse/{issue['key']}",
                })
            return results
        except httpx.HTTPError as e:
            logger.error("Failed to list Jira issues: %s", e)
            return []

    async def list_members(self) -> List[dict]:
        """Return all users with access to the project."""
        try:
            resp = await self.client.get(
                f"{self._api}/user/assignable/search",
                params={"project": self.project, "maxResults": 200},
            )
            resp.raise_for_status()
            return [
                {"displayName": u.get("displayName", ""), "uniqueName": u.get("accountId", "")}
                for u in resp.json()
                if u.get("active", True)
            ]
        except httpx.HTTPError as e:
            logger.warning("list_members failed: %s", e)
            return []

    async def resolve_user(self, name: str) -> Optional[str]:
        """Search for a Jira user by name, return their accountId."""
        try:
            resp = await self.client.get(f"{self._api}/user/search", params={"query": name})
            resp.raise_for_status()
            for user in resp.json():
                if name.lower() in user.get("displayName", "").lower():
                    account_id = user.get("accountId")
                    logger.info("Resolved '%s' → accountId=%s", name, account_id)
                    return account_id
        except httpx.HTTPError as e:
            logger.warning("resolve_user failed: %s", e)
        logger.warning("Could not resolve Jira user '%s'", name)
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _apply_transition(self, issue_key: str, target_status: str) -> None:
        """
        Find the transition whose name matches *target_status* and apply it.

        Jira does not allow setting status directly — you must POST to
        /issue/{key}/transitions with the matching transition ID.
        """
        try:
            resp = await self.client.get(f"{self._api}/issue/{issue_key}/transitions")
            resp.raise_for_status()
            transitions = resp.json().get("transitions", [])
            match = next(
                (t for t in transitions if t["to"]["name"].lower() == target_status.lower()),
                None,
            )
            if not match:
                logger.warning(
                    "No Jira transition found to '%s' for issue %s. Available: %s",
                    target_status, issue_key, [t["to"]["name"] for t in transitions],
                )
                return
            transition_resp = await self.client.post(
                f"{self._api}/issue/{issue_key}/transitions",
                json={"transition": {"id": match["id"]}},
            )
            transition_resp.raise_for_status()
            logger.info("Transitioned %s → %s", issue_key, target_status)
        except httpx.HTTPError as e:
            logger.error("Failed to apply transition for %s: %s", issue_key, e)

    @staticmethod
    def _to_adf(text: str) -> Dict[str, Any]:
        """Convert a plain-text string to minimal Atlassian Document Format."""
        return {
            "version": 1,
            "type":    "doc",
            "content": [
                {
                    "type":    "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        }

    @staticmethod
    def _from_adf(adf: Any) -> str:
        """Extract plain text from an ADF document (best-effort)."""
        if adf is None:
            return ""
        if isinstance(adf, str):
            return adf
        parts = []
        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "text":
                    parts.append(node.get("text", ""))
                for child in node.get("content", []):
                    _walk(child)
            elif isinstance(node, list):
                for child in node:
                    _walk(child)
        _walk(adf)
        return " ".join(parts).strip()

    def _is_transient(self, error: httpx.HTTPError) -> bool:
        """Return True if the error is likely temporary and worth retrying."""
        if hasattr(error, "response") and error.response is not None:
            return error.response.status_code in (429, 502, 503, 504)
        return "timeout" in str(error).lower() or "connection" in str(error).lower()
