"""AI-powered ticket parser that extracts structured data from natural language"""
import json
import re
from typing import Dict, Any, Optional
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
    
    def parse(self, user_input: str) -> ParsedTicket:
        """
        Parse natural language input into structured ticket data.
        
        Args:
            user_input: Natural language description of the ticket
            
        Returns:
            ParsedTicket with extracted information
            
        Example:
            Input: "Create a high priority bug ticket for Jamie to fix the login issue"
            Output: ParsedTicket(
                title="Fix the login issue",
                description="Fix the login issue",
                assignee="Jamie",
                priority="High",
                ticket_type="Bug"
            )
        """
        # Extract assignee
        assignee = self._extract_assignee(user_input)
        
        # Extract priority
        priority = self._extract_priority(user_input)
        
        # Extract ticket type
        ticket_type = self._extract_type(user_input)
        
        # Extract title and description
        title, description = self._extract_title_and_description(user_input)
        
        # Extract labels
        labels = self._extract_labels(user_input)
        
        return ParsedTicket(
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            ticket_type=ticket_type,
            labels=labels
        )
    
    def _extract_assignee(self, text: str) -> Optional[str]:
        """Extract assignee name from text"""
        # Pattern: "assigned to X", "for X to", "assign X"
        patterns = [
            r"@(\w+)",                                              # @mention (highest priority)
            r"assigned?\s+to\s+(\w+)",
            r"for\s+(\w+)\s+to",
            r"assign\s+(\w{2,})",                                   # "assign X" — skip single chars like "a"
            r"(\w+)\s+needs\s+a?\s*(?:ticket|task|bug|issue|fix)",
            r"(\w+)\s+should\s+(?:fix|handle|work\s+on|do)\s+",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        
        return None
    
    def _extract_priority(self, text: str) -> str:
        """Extract priority from text"""
        text_lower = text.lower()
        
        for keyword, priority in self.priority_keywords.items():
            if keyword in text_lower:
                return priority
        
        return "Medium"  # Default
    
    def _extract_type(self, text: str) -> str:
        """Extract ticket type from text"""
        text_lower = text.lower()
        
        for keyword, ticket_type in self.type_keywords.items():
            if keyword in text_lower:
                return ticket_type
        
        return "Task"  # Default
    
    def _extract_title_and_description(self, text: str) -> tuple[str, str]:
        """Extract title and description from text"""
        # Remove common prefixes
        cleaned = re.sub(
            r"^(create|write|make|add|new)\s+(a\s+)?(ticket|task|bug|issue|story)\s+",
            "",
            text,
            flags=re.IGNORECASE
        )
        
        # Remove @mentions (e.g. @piram, @behniwalp36@gmail.com)
        cleaned = re.sub(r"@\S+", "", cleaned, flags=re.IGNORECASE)

        # Remove assignee mentions
        cleaned = re.sub(r"(assigned?\s+to|for)\s+\w+\s+(to\s+)?", "", cleaned, flags=re.IGNORECASE)
        
        # Remove priority mentions
        for keyword in self.priority_keywords.keys():
            cleaned = re.sub(rf"\b{keyword}\s+(priority\s+)?", "", cleaned, flags=re.IGNORECASE)
        
        # Remove type mentions
        for keyword in self.type_keywords.keys():
            cleaned = re.sub(rf"\b{keyword}\s+", "", cleaned, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        
        # Use the same text for both title and description
        # In production, you might want to generate a more detailed description
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
    Enhanced parser using Claude (Anthropic) for natural language understanding.
    Falls back to regex pattern matching when no API key is available.
    """

    _SYSTEM_PROMPT = """\
You extract structured ticket information from natural language requests.

Respond with a single JSON object — no markdown, no explanation — using these exact keys:
{
  "title":       "<concise action title, ≤80 chars>",
  "description": "<fuller description or same as title if nothing extra>",
  "assignee":    "<first or full name, or null>",
  "priority":    "<Critical|High|Medium|Low>",
  "ticket_type": "<Bug|Feature|Task|User Story>",
  "labels":      ["<label>", ...]
}

Rules:
- title must be an actionable phrase, not the raw user sentence
- priority defaults to Medium when not mentioned
- ticket_type defaults to Task when not clear
- labels: include tech area keywords (security, backend, frontend, database, mobile, api, auth) if mentioned; also include any #hashtags
- assignee: null if no person is mentioned
"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self._client = None
        if api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                pass  # falls back to regex

    def parse(self, user_input: str) -> ParsedTicket:
        if self._client:
            try:
                return self._parse_with_claude(user_input)
            except Exception:
                pass  # fall through to regex on any error
        return super().parse(user_input)

    def _parse_with_claude(self, user_input: str) -> ParsedTicket:
        import anthropic
        message = self._client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            system=self._SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input}],
        )
        raw = message.content[0].text.strip()
        data: Dict[str, Any] = json.loads(raw)
        return ParsedTicket(
            title=data.get("title", user_input[:80]),
            description=data.get("description", user_input),
            assignee=data.get("assignee") or None,
            priority=data.get("priority", "Medium"),
            ticket_type=data.get("ticket_type", "Task"),
            labels=data.get("labels", []),
        )
