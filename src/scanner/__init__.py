"""Codebase scanner — surfaces work that needs doing as ticket suggestions."""
from .todo_scanner import scan_workspace, Suggestion

__all__ = ["scan_workspace", "Suggestion"]
