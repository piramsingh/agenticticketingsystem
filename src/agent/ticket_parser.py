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
            r"assigned?\s+to\s+(\w+)",
            r"for\s+(\w+)\s+to",
            r"assign\s+(\w+)",
            r"@(\w+)",
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
    Enhanced parser using LLM for better natural language understanding.
    
    This would use OpenAI, Anthropic, or other LLM APIs in production.
    For demo purposes, falls back to pattern matching.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM parser.
        
        Args:
            api_key: API key for LLM service (OpenAI, Anthropic, etc.)
        """
        super().__init__()
        self.api_key = api_key
        self.use_llm = api_key is not None
    
    def parse(self, user_input: str) -> ParsedTicket:
        """
        Parse using LLM if available, otherwise fall back to pattern matching.
        
        Args:
            user_input: Natural language description
            
        Returns:
            ParsedTicket with extracted information
        """
        if self.use_llm:
            return self._parse_with_llm(user_input)
        else:
            # Fall back to pattern matching
            return super().parse(user_input)
    
    def _parse_with_llm(self, user_input: str) -> ParsedTicket:
        """
        Parse using LLM API.
        
        This is a placeholder for actual LLM integration.
        In production, you would call OpenAI/Anthropic API here.
        """
        # TODO: Implement actual LLM API call
        # Example with OpenAI:
        # response = openai.ChatCompletion.create(
        #     model="gpt-4",
        #     messages=[
        #         {"role": "system", "content": "Extract ticket information from user input..."},
        #         {"role": "user", "content": user_input}
        #     ]
        # )
        
        # For now, fall back to pattern matching
        return super().parse(user_input)
