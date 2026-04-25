"""
GitHub Issues connector.

Auth:    Bearer <personal access token>
Base:    https://api.github.com
Project: "owner/repo" (e.g. "piramsingh/agenticticketingsystem")

GitHub doesn't have an issue type concept — type and priority are both
expressed as labels. The connector maps canonical inputs to common label
conventions ("bug", "enhancement", "priority:high").
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseConnector
from ..models.ticket import Activity, CreateItemResult, TargetItem, WebhookEvent

logger = logging.getLogger(__name__)


class GitHubIssuesConnector(BaseConnector):
    """
    GitHub Issues connector (REST API v3).

    Project identifier is "owner/repo". Type and priority are surfaced as
    labels because GitHub has no first-class concept for either.
    """

    # Canonical → GitHub label (lowercase, GitHub convention)
    _PRIORITY_MAP: Dict[str, str] = {
        "critical": "priority:critical",
        "high":     "priority:high",
        "medium":   "priority:medium",
        "low":      "priority:low",
    }

    _TYPE_MAP: Dict[str, str] = {
        "bug":        "bug",
        "feature":    "enhancement",
        "task":       "task",
        "user story": "enhancement",
    }

    def __init__(self, base_url: str, token: str, project: str):
        # base_url is typically https://api.github.com
        self.base_url = base_url.rstrip("/")
        self.project = project   # "owner/repo"
        self._repo_url = f"{self.base_url}/repos/{self.project}"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept":        "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    # ── Field normalisation ───────────────────────────────────────────────────

    def normalize_priority(self, canonical: str) -> str:
        return self._PRIORITY_MAP.get(canonical.lower(), "priority:medium")

    def normalize_type(self, canonical: str) -> str:
        # Pass-through for unknown types so LLM picks (e.g. "documentation") survive
        return self._TYPE_MAP.get(canonical.lower(), canonical.lower())

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_item(self, fields: Dict[str, Any]) -> CreateItemResult:
        """Create a GitHub issue. Type + priority go in as labels."""
        labels: List[str] = []

        type_label = fields.pop("type", None)
        if type_label:
            labels.append(str(type_label))

        priority_label = fields.get("priority")
        if priority_label:
            labels.append(str(priority_label))

        if "tags" in fields and fields["tags"]:
            labels.extend(t.strip() for t in str(fields["tags"]).split(",") if t.strip())

        body: Dict[str, Any] = {
            "title": fields.get("title", "Untitled"),
            "body":  fields.get("description", ""),
            "labels": list(dict.fromkeys(labels)),  # dedupe preserving order
        }

        if "assignee_id" in fields and fields["assignee_id"]:
            body["assignees"] = [fields["assignee_id"]]

        logger.info("Creating GitHub issue in %s", self.project)

        for attempt, delay in enumerate([1, 2, 4]):
            try:
                resp = await self.client.post(f"{self._repo_url}/issues", json=body)
                if resp.status_code == 422 and body.get("labels"):
                    logger.warning(
                        "GitHub 422 on create — likely missing labels %s. Retrying without labels. Body: %s",
                        body["labels"], resp.text,
                    )
                    body.pop("labels")
                    resp = await self.client.post(f"{self._repo_url}/issues", json=body)
                if resp.status_code == 422:
                    logger.error("GitHub 422 — request: %s — response: %s", body, resp.text)
                resp.raise_for_status()
                data = resp.json()
                return CreateItemResult(
                    item_id=str(data["number"]),
                    item_url=data["html_url"],
                    created_at=datetime.utcnow(),
                )
            except httpx.HTTPStatusError as e:
                if self._is_transient(e) and attempt < 2:
                    logger.warning("Transient error, retrying in %ds: %s", delay, e)
                    await asyncio.sleep(delay)
                    continue
                detail = e.response.text if e.response is not None else ""
                logger.error("Failed to create GitHub issue: %s — %s", e, detail)
                raise RuntimeError(f"GitHub rejected the request: {detail}") from e

    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> None:
        """Update a GitHub issue. Maps title/description/state/labels."""
        body: Dict[str, Any] = {}
        if "title" in fields:
            body["title"] = fields["title"]
        if "description" in fields:
            body["body"] = fields["description"]
        if "status" in fields or "state" in fields:
            new_state = (fields.get("status") or fields.get("state") or "").lower()
            # GitHub only has open/closed
            body["state"] = "closed" if new_state in ("done", "closed", "resolved") else "open"
        if "assignee_id" in fields and fields["assignee_id"]:
            body["assignees"] = [fields["assignee_id"]]

        if not body:
            return

        try:
            resp = await self.client.patch(f"{self._repo_url}/issues/{item_id}", json=body)
            resp.raise_for_status()
            logger.info("Updated GitHub issue #%s", item_id)
        except httpx.HTTPError as e:
            logger.error("Failed to update GitHub issue #%s: %s", item_id, e)
            raise

    async def get_item(self, item_id: str) -> TargetItem:
        """Retrieve a GitHub issue by number."""
        try:
            resp = await self.client.get(f"{self._repo_url}/issues/{item_id}")
            resp.raise_for_status()
            data = resp.json()
            updated_str = data.get("updated_at") or data.get("created_at")
            last_modified = (
                datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if updated_str else datetime.utcnow()
            )
            label_names = [l["name"] for l in data.get("labels", []) if isinstance(l, dict)]
            priority = next((l for l in label_names if l.startswith("priority:")), "")
            return TargetItem(
                item_id=str(data["number"]),
                title=data.get("title", ""),
                description=data.get("body") or "",
                status=data.get("state", ""),
                priority=priority,
                last_modified=last_modified,
                fields=data,
            )
        except httpx.HTTPError as e:
            logger.error("Failed to get GitHub issue #%s: %s", item_id, e)
            raise

    # ── Webhooks ──────────────────────────────────────────────────────────────

    def parse_webhook(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse a GitHub `issues` webhook event."""
        try:
            action = payload.get("action", "")
            type_map = {"opened": "created", "edited": "updated", "closed": "updated", "reopened": "updated", "deleted": "deleted"}
            event_type = type_map.get(action, "updated")

            issue = payload.get("issue", {})
            item_id = str(issue.get("number", ""))
            if not item_id:
                raise ValueError("Missing issue number in webhook payload")

            updated_fields: Dict[str, Any] = {}
            changes = payload.get("changes", {})
            if "title" in changes:
                updated_fields["title"] = issue.get("title", "")
            if "body" in changes:
                updated_fields["description"] = issue.get("body", "")
            if action in ("closed", "reopened"):
                updated_fields["status"] = issue.get("state", "")

            return WebhookEvent(
                event_type=event_type,
                item_id=item_id,
                updated_fields=updated_fields,
                timestamp=datetime.utcnow(),
            )
        except (KeyError, ValueError) as e:
            logger.error("Failed to parse GitHub webhook: %s", e)
            raise ValueError(f"Invalid GitHub webhook payload: {e}")

    # ── Connectivity ──────────────────────────────────────────────────────────

    async def validate_connection(self) -> bool:
        """Verify the token can read the repo."""
        try:
            resp = await self.client.get(self._repo_url)
            resp.raise_for_status()
            logger.info("GitHub connection validated for %s", self.project)
            return True
        except httpx.HTTPError as e:
            logger.error("GitHub connection validation failed: %s", e)
            return False

    # ── Type discovery (labels) ───────────────────────────────────────────────

    async def get_valid_types(self) -> List[str]:
        """
        Return the repo's existing labels so the parser picks from real ones.
        GitHub doesn't have first-class types; labels are how teams categorise.
        """
        try:
            resp = await self.client.get(f"{self._repo_url}/labels", params={"per_page": 100})
            resp.raise_for_status()
            return [lbl["name"] for lbl in resp.json()]
        except httpx.HTTPError as e:
            logger.warning("Could not fetch GitHub labels: %s", e)
            return []

    # ── Listing ───────────────────────────────────────────────────────────────

    async def list_items(self, limit: int = 10) -> List[dict]:
        """Return recent issues sorted by updated date."""
        limit = min(limit, 50)
        try:
            resp = await self.client.get(
                f"{self._repo_url}/issues",
                params={"sort": "updated", "direction": "desc", "per_page": limit, "state": "all"},
            )
            resp.raise_for_status()
            results = []
            for issue in resp.json():
                # GitHub's /issues endpoint also returns PRs — filter them out
                if "pull_request" in issue:
                    continue
                assignee = issue.get("assignee") or {}
                label_names = [l["name"] for l in issue.get("labels", []) if isinstance(l, dict)]
                priority = next((l for l in label_names if l.startswith("priority:")), "")
                results.append({
                    "id":         str(issue["number"]),
                    "title":      issue.get("title", ""),
                    "status":     issue.get("state", ""),
                    "priority":   priority,
                    "assignedTo": assignee.get("login", "Unassigned") if assignee else "Unassigned",
                    "url":        issue.get("html_url", ""),
                })
            return results
        except httpx.HTTPError as e:
            logger.error("Failed to list GitHub issues: %s", e)
            return []

    async def list_members(self) -> List[dict]:
        """Return repo collaborators for @mention autocomplete."""
        try:
            resp = await self.client.get(f"{self._repo_url}/collaborators", params={"per_page": 100})
            resp.raise_for_status()
            return [
                {"displayName": u.get("login", ""), "uniqueName": u.get("login", "")}
                for u in resp.json()
            ]
        except httpx.HTTPError as e:
            logger.warning("list_members failed (token may lack scope): %s", e)
            return []

    async def resolve_user(self, name: str) -> Optional[str]:
        """Match a name against repo collaborators, return GitHub login."""
        try:
            members = await self.list_members()
            target = name.lower()
            for m in members:
                if target in m["displayName"].lower():
                    return m["uniqueName"]
        except Exception as e:
            logger.warning("resolve_user failed: %s", e)
        logger.warning("Could not resolve GitHub user '%s'", name)
        return None

    async def close(self) -> None:
        await self.client.aclose()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_transient(self, error: httpx.HTTPError) -> bool:
        if hasattr(error, "response") and error.response is not None:
            return error.response.status_code in (429, 502, 503, 504)
        return "timeout" in str(error).lower() or "connection" in str(error).lower()
