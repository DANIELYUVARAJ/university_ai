"""
University DataShield - LLM Assistant API Router
Phase 13: Local AI Assistant Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from .schemas import (
    AssistantStatusResponse,
    QuestionRequest,
    QuestionResponse,
    ExplainScanRequest,
    ExplainScanResponse,
)
from .service import LLMAssistantService

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.get("/status", response_model=AssistantStatusResponse)
async def get_assistant_status():
    """Get status of the local LLM assistant provider (Ollama)."""
    return await LLMAssistantService.check_ollama_status()


@router.post("/ask", response_model=QuestionResponse)
async def ask_assistant(request: QuestionRequest):
    """
    Ask a question about sensitive fields, FERPA, or masking transformations.
    Advisory only: Cannot authorize publication or modify policies.
    """
    return await LLMAssistantService.ask_question(request)


@router.post("/explain-scan", response_model=ExplainScanResponse)
async def explain_scan(request: ExplainScanRequest):
    """
    Explain findings from a synthetic schema scan, provide policy recommendations,
    and cross-check each recommendation with the authoritative deterministic PolicyEngine.
    """
    return await LLMAssistantService.explain_scan(request)
