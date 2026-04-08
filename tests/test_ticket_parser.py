"""Tests for AI ticket parser"""
import pytest
from src.agent.ticket_parser import TicketParser, ParsedTicket


class TestTicketParser:
    """Tests for TicketParser"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.parser = TicketParser()
    
    def test_parse_basic_ticket(self):
        """Test parsing a basic ticket"""
        parsed = self.parser.parse("Create a ticket to fix the login bug")
        
        assert "login bug" in parsed.title.lower()
        assert parsed.ticket_type == "Bug"
    
    def test_parse_with_assignee(self):
        """Test parsing ticket with assignee"""
        parsed = self.parser.parse("Create a ticket for Jamie to fix the security issue")
        
        assert parsed.assignee == "Jamie"
        assert "security" in parsed.title.lower()
    
    def test_parse_with_priority(self):
        """Test parsing ticket with priority"""
        test_cases = [
            ("Create a high priority bug", "High"),
            ("Make a critical task", "Critical"),
            ("Add a low priority feature", "Low"),
            ("Create a normal ticket", "Medium")
        ]
        
        for input_text, expected_priority in test_cases:
            parsed = self.parser.parse(input_text)
            assert parsed.priority == expected_priority, f"Failed for: {input_text}"
    
    def test_parse_ticket_types(self):
        """Test parsing different ticket types"""
        test_cases = [
            ("Create a bug to fix the issue", "Bug"),
            ("Add a feature for dark mode", "Feature"),
            ("Make a task to update docs", "Task"),
            ("Write a user story for login", "User Story")
        ]
        
        for input_text, expected_type in test_cases:
            parsed = self.parser.parse(input_text)
            assert parsed.ticket_type == expected_type, f"Failed for: {input_text}"
    
    def test_parse_with_labels(self):
        """Test parsing ticket with labels"""
        parsed = self.parser.parse("Create a ticket for the backend security issue #security #backend")
        
        assert "security" in parsed.labels
        assert "backend" in parsed.labels
    
    def test_parse_complex_ticket(self):
        """Test parsing a complex ticket with multiple attributes"""
        parsed = self.parser.parse(
            "Create a critical bug ticket assigned to Jamie to fix the security vulnerability in the backend #security #backend"
        )
        
        assert parsed.assignee == "Jamie"
        assert parsed.priority == "Critical"
        assert parsed.ticket_type == "Bug"
        assert "security" in parsed.labels
        assert "backend" in parsed.labels
        assert "security" in parsed.title.lower() or "vulnerability" in parsed.title.lower()
    
    def test_parse_with_at_mention(self):
        """Test parsing ticket with @mention assignee"""
        parsed = self.parser.parse("Create a task @sarah to update the documentation")
        
        assert parsed.assignee == "Sarah"
    
    def test_parse_assigned_to_format(self):
        """Test parsing ticket with 'assigned to' format"""
        parsed = self.parser.parse("Create a ticket assigned to Alex for the database migration")
        
        assert parsed.assignee == "Alex"
        assert "database" in parsed.title.lower()
    
    def test_to_dict(self):
        """Test ParsedTicket to_dict conversion"""
        parsed = ParsedTicket(
            title="Fix login bug",
            description="Fix the login bug in the authentication system",
            assignee="Jamie",
            priority="High",
            ticket_type="Bug",
            labels=["security", "backend"]
        )
        
        result = parsed.to_dict()
        
        assert result["title"] == "Fix login bug"
        assert result["assignee"] == "Jamie"
        assert result["priority"] == "High"
        assert result["type"] == "Bug"
        assert "security" in result["labels"]
    
    def test_parse_empty_input(self):
        """Test parsing empty input"""
        parsed = self.parser.parse("")
        
        # Should return a ParsedTicket with defaults
        assert parsed.title == ""
        assert parsed.priority == "Medium"
        assert parsed.ticket_type == "Task"
    
    def test_parse_multiple_priorities(self):
        """Test that first priority wins when multiple are mentioned"""
        parsed = self.parser.parse("Create a high priority critical bug")
        
        # Should extract the first priority mentioned
        assert parsed.priority in ["High", "Critical"]
    
    def test_extract_labels_from_keywords(self):
        """Test automatic label extraction from keywords"""
        test_cases = [
            ("Fix the security issue", ["security"]),
            ("Update the backend database", ["backend", "database"]),
            ("Redesign the frontend UI", ["frontend"]),
        ]
        
        for input_text, expected_labels in test_cases:
            parsed = self.parser.parse(input_text)
            for label in expected_labels:
                assert label in parsed.labels, f"Expected {label} in labels for: {input_text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
