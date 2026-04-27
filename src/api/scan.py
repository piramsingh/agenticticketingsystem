"""
Codebase scan endpoint — surfaces ticket suggestions from a workspace path.

The extension sends the active workspace path (it knows it via the VS Code API);
the backend walks the tree and returns suggestions matching the UI contract.

Runs the regex pass always; runs the LLM pass automatically when
OPENROUTER_API_KEY is set in the environment.
"""
import asyncio
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..scanner import scan_workspace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["scan"])


class ScanRequest(BaseModel):
    workspace_path: str = Field(..., description="Absolute path to the project root")
    limit: Optional[int] = Field(default=100, ge=1, le=500)


class SuggestionOut(BaseModel):
    id: str
    type: str
    title: str
    file: str
    line: int
    snippet: str


class ScanResponse(BaseModel):
    suggestions: List[SuggestionOut]
    count: int


@router.post("/suggestions", response_model=ScanResponse)
async def scan_suggestions(req: ScanRequest) -> ScanResponse:
    """
    Scan *workspace_path* for ticket suggestions.

    - Always runs the regex pass (TODO/FIXME/HACK/XXX comment markers).
    - When OPENROUTER_API_KEY is set, also runs the LLM pass for non-marker
      issues (bugs, refactors, missing tests).
    """
    llm_key = os.getenv("OPENROUTER_API_KEY")
    try:
        # File I/O + LLM calls are blocking; offload so the event loop stays free.
        suggestions = await asyncio.to_thread(
            scan_workspace,
            req.workspace_path,
            req.limit,
            llm_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Scan failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")

    return ScanResponse(
        suggestions=[SuggestionOut(**s.to_dict()) for s in suggestions],
        count=len(suggestions),
    )
