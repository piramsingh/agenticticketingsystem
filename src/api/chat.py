"""Chat API endpoint for natural language ticket creation"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..agent.chat_agent import ChatAgent
from ..agent.ticket_parser import TicketParser


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Global chat agent instance (set by main.py)
_chat_agent: ChatAgent | None = None


def set_chat_agent(agent: ChatAgent):
    """Set the global chat agent instance"""
    global _chat_agent
    _chat_agent = agent


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    success: bool
    parsed: Dict[str, Any] | None = None
    target_ticket: Dict[str, Any] | None = None
    jama_requirement: Dict[str, Any] | None = None
    message: str
    error: str | None = None


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process natural language message and create tickets.
    
    Args:
        request: Chat request with user message
        
    Returns:
        ChatResponse with ticket creation results
        
    Example:
        POST /chat
        {
            "message": "Create a ticket for Jamie to fix the security issue"
        }
    """
    if not _chat_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat agent not initialized"
        )
    
    try:
        logger.info(f"Processing chat message: {request.message}")
        result = await _chat_agent.process_message(request.message)
        logger.info(f"Chat processing result: {result}")
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.get("/help")
async def get_help() -> Dict[str, str]:
    """
    Get help message explaining how to use the chat agent.
    
    Returns:
        Dictionary with help message
    """
    if not _chat_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat agent not initialized"
        )
    
    return {
        "help": _chat_agent.get_help_message()
    }
