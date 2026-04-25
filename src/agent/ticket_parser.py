"""AI-powered ticket parser that extracts structured data from natural language"""
import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ParsedTicket:
    """Structured ticket data extracted from natural language"""
    title: str
    description: str
    assignee: Optional[str] = None
    priority: str = "Medium"
    ticket_type: str = "Task"
    labels: list = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            "title": self.title,
            "description": self.description,
            "assignee": self.assignee,
            "priority": self.priority,
            "type": self.ticket_type,
            "labels": self.labels
        }


class TicketParser:
    """
    Parses natural language input into structured ticket data.
    
    Uses pattern matching and keyword extraction to understand user intent.
    In production, this would use an LLM API (OpenAI, Anthropic, etc.)
    """
    
    def __init__(self):
        """Initialize parser with patterns"""
        self.priority_keywords = {
            "critical": "Critical",
            "urgent": "Critical",
            "high": "High",
            "important": "High",
            "medium": "Medium",
            "normal": "Medium",
            "low": "Low",
            "minor": "Low"
        }
        
        self.type_keywords = {
            "bug": "Bug",
            "issue": "Bug",
            "fix": "Bug",
            "feature": "Feature",
            "enhancement": "Feature",
            "task": "Task",
            "story": "User Story",
            "user story": "User Story"
        }

        # Intent → keywords that indicate each category (for fuzzy matching against real types)
        self._intent_hints: Dict[str, List[str]] = {
            "Bug":        ["bug", "defect", "error", "issue", "fix"],
            "Feature":    ["feature", "story", "enhancement", "epic"],
            "Task":       ["task", "chore", "work", "todo"],
            "User Story": ["story", "user story", "feature"],
        }
    
    def match_to_valid_type(self, intent: str, valid_types: List[str]) -> str:
        """Given a canonical intent ('Bug', 'Feature', …) pick the closest valid type."""
        if not valid_types:
            return intent
        if intent in valid_types:
            return intent
        lower_valid = {t.lower(): t for t in valid_types}
        if intent.lower() in lower_valid:
            return lower_valid[intent.lower()]
        hints = self._intent_hints.get(intent, [intent.lower()])
        for hint in hints:
            for vt in valid_types:
                if hint in vt.lower():
                    return vt
        # Last resort: prefer Task (most generic) over the arbitrary first item
        return next((t for t in valid_types if t.lower() == "task"), valid_types[0])

    def parse(self, user_input: str, valid_types: Optional[List[str]] = None) -> ParsedTicket:
        """
        Parse natural language input into structured ticket data.

        Args:
            user_input:  Natural language description of the ticket.
            valid_types: Real type names from the target platform (optional).
                         When provided, the extracted type is matched against
                         this list so it's always a value the API accepts.
        """
        assignee = self._extract_assignee(user_input)
        priority = self._extract_priority(user_input)
        ticket_type = self._extract_type(user_input)
        title, description = self._extract_title_and_description(user_input)
        labels = self._extract_labels(user_input)

        if valid_types:
            ticket_type = self.match_to_valid_type(ticket_type, valid_types)

        return ParsedTicket(
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            ticket_type=ticket_type,
            labels=labels
        )
    
    def _extract_assignee(self, text: str) -> Optional[str]:
        """Extract assignee name from text, including multi-word names after @."""
        # @mention: first name + optional one last name, e.g. "@Piram Singh"
        m = re.search(r"@(\w+(?:\s+[A-Z][a-z]+)?)", text)
        if m:
            return m.group(1).replace("_", " ")

        # Prose patterns — require proper nouns (capital first letter) to avoid false positives
        patterns = [
            r"assign(?:ed)?\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"for\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+to\b",
            r"assign\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"([A-Z][a-z]+)\s+needs\s+a?\s*(?:ticket|task|bug|issue|fix)",
            r"([A-Z][a-z]+)\s+should\s+(?:fix|handle|work\s+on|do)\s+",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return None
    
    def _extract_priority(self, text: str) -> str:
        """Extract priority from text using whole-word matching."""
        for keyword, priority in self.priority_keywords.items():
            if re.search(rf"\b{keyword}\b", text, re.IGNORECASE):
                return priority
        return "Medium"
    
    def _extract_type(self, text: str) -> str:
        """Extract ticket type from text"""
        text_lower = text.lower()
        
        for keyword, ticket_type in self.type_keywords.items():
            if keyword in text_lower:
                return ticket_type
        
        return "Task"  # Default
    
    def _extract_title_and_description(self, text: str) -> tuple[str, str]:
        # 1. Strip @mention including optional one last name: "@Piram Singh"
        cleaned = re.sub(r"@\w+(?:\s+[A-Z][a-z]+)?", "", text)

        # 2. Strip "Create a story/bug/task/… [to]" prefix at the start
        cleaned = re.sub(
            r"^\s*(create|write|make|add|new)\s+(a\s+|an\s+)?"
            r"(ticket|task|bug|issue|story|feature|epic|user\s+story)"
            r"[\s,:;]+(to\s+)?",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        # 3. Strip assignee prose — only match proper nouns (capital first letter)
        #    so "for the Carplay" is NOT removed
        cleaned = re.sub(
            r"\b(assign(?:ed)?\s+to|for)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s*(to\s+)?",
            "",
            cleaned,
        )

        # 4. Strip priority words
        for keyword in self.priority_keywords:
            cleaned = re.sub(rf"\b{keyword}\s+(priority\s+)?", "", cleaned, flags=re.IGNORECASE)

        # 5. Strip a leading type keyword now that priority/assignee noise is gone
        type_prefix = "|".join(re.escape(k) for k in self.type_keywords)
        cleaned = re.sub(rf"^\s*({type_prefix})[:\s]+", "", cleaned, flags=re.IGNORECASE)

        # 6. Strip leading filler words left over after prefix removals
        cleaned = re.sub(r"^\s*(for|to|a|an|the|about)\s+", "", cleaned, flags=re.IGNORECASE)

        # 7. Strip trailing punctuation
        cleaned = cleaned.strip(" .,;:")

        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned, cleaned
    
    def _extract_labels(self, text: str) -> list:
        """Extract labels/tags from text"""
        labels = []
        
        # Look for hashtags
        hashtags = re.findall(r"#(\w+)", text)
        labels.extend(hashtags)
        
        # Look for common label keywords
        if "security" in text.lower():
            labels.append("security")
        if "backend" in text.lower() or "back-end" in text.lower():
            labels.append("backend")
        if "frontend" in text.lower() or "front-end" in text.lower():
            labels.append("frontend")
        if "database" in text.lower() or "db" in text.lower():
            labels.append("database")
        
        return list(set(labels))  # Remove duplicates


class LLMTicketParser(TicketParser):
    """
    LLM-powered parser using OpenRouter (OpenAI-compatible API).
    Falls back to regex when no API key is set or the call fails.
    """

    _OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    # Tried in order — if one is rate-limited (429), we move to the next
    _MODEL_FALLBACKS = [
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
    ]

    _SYSTEM_PROMPT = """\
You extract structured ticket information from natural language requests.

Respond with a single JSON object — no markdown, no explanation — using these exact keys:
{
  "title":       "<concise actionable title, ≤80 chars>",
  "description": "<fuller description, or same as title if nothing extra>",
  "assignee":    "<first or full name, or null>",
  "priority":    "<Critical|High|Medium|Low>",
  "ticket_type": "<Bug|Feature|Task|User Story|Epic>",
  "labels":      ["<label>", ...]
}

Rules:
- title must be an actionable phrase, not the raw user sentence
- @mentions indicate the assignee (e.g. "@Piram Singh" → assignee: "Piram Singh")
- priority defaults to Medium when not mentioned
- ticket_type: use Epic for large initiatives spanning multiple stories; Story/Feature for single user-facing features; Bug for defects; Task for chores
- ticket_type defaults to Task when not clear
- labels: include tech area keywords (security, backend, frontend, database, mobile, api, auth) if mentioned; also include any #hashtags
- assignee: null if no person is mentioned
"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._api_key = api_key

    def parse(self, user_input: str, valid_types: Optional[List[str]] = None) -> ParsedTicket:
        if self._api_key:
            try:
                return self._parse_with_llm(user_input, valid_types)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("LLM parse failed, falling back to regex: %s", e)
        return super().parse(user_input, valid_types)

    def _parse_with_llm(self, user_input: str, valid_types: Optional[List[str]] = None) -> ParsedTicket:
        import httpx
        import time
        import logging
        log = logging.getLogger(__name__)

        system = self._SYSTEM_PROMPT
        if valid_types:
            type_list = ", ".join(f'"{t}"' for t in valid_types)
            system += f"\n- ticket_type MUST be one of these exact values: {type_list}"

        last_error: Optional[Exception] = None
        for model in self._MODEL_FALLBACKS:
            for attempt, backoff in enumerate([0, 2, 5]):
                if backoff:
                    time.sleep(backoff)
                try:
                    resp = httpx.post(
                        self._OPENROUTER_URL,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": user_input},
                            ],
                            "max_tokens": 512,
                            "temperature": 0.1,
                        },
                        timeout=20.0,
                    )
                    if resp.status_code == 429:
                        retry_after = resp.headers.get("retry-after") or "?"
                        log.warning(
                            "Rate limited on %s (attempt %d, retry-after=%s)",
                            model, attempt + 1, retry_after,
                        )
                        last_error = Exception(f"429 on {model}")
                        continue  # next attempt with backoff
                    resp.raise_for_status()
                    raw = resp.json()["choices"][0]["message"]["content"].strip()
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                    data: Dict[str, Any] = json.loads(raw)
                    ticket_type = data.get("ticket_type", "Task")
                    if valid_types:
                        ticket_type = self.match_to_valid_type(ticket_type, valid_types)
                    log.info("LLM parse succeeded with %s", model)
                    return ParsedTicket(
                        title=data.get("title", user_input[:80]),
                        description=data.get("description", user_input),
                        assignee=data.get("assignee") or None,
                        priority=data.get("priority", "Medium"),
                        ticket_type=ticket_type,
                        labels=data.get("labels", []),
                    )
                except httpx.HTTPError as e:
                    last_error = e
                    log.warning("Model %s failed: %s", model, e)
                    break  # this model is broken, try next
            log.warning("Exhausted retries on %s, trying next model", model)

        # All models exhausted — raise to trigger regex fallback in parse()
        raise last_error or RuntimeError("All OpenRouter models failed")
