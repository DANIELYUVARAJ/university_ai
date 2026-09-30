# backend/pipeline/jobs.py
"""
Pipeline Job models and extended state machine for Phase 11.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .schemas import PipelineValidateRequest, PipelineValidateResponse


class JobState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SCANNING = "SCANNING"
    DETECTED = "DETECTED"
    VALIDATING_POLICY = "VALIDATING_POLICY"
    VALIDATING_ACCESS = "VALIDATING_ACCESS"
    READY = "READY"
    BLOCKED = "BLOCKED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineJob(BaseModel):
    job_id: str
    pipeline_id: str
    execution_id: str
    dataset_name: str
    state: JobState = JobState.CREATED
    retry_count: int = 0
    max_retries: int = 3
    request_payload: PipelineValidateRequest
    result: Optional[PipelineValidateResponse] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def mark_queued(self) -> None:
        self.state = JobState.QUEUED

    def mark_running(self) -> None:
        self.state = JobState.RUNNING
        self.started_at = datetime.utcnow().isoformat() + "Z"

    def mark_completed(self, result: PipelineValidateResponse) -> None:
        self.result = result
        self.completed_at = datetime.utcnow().isoformat() + "Z"
        # Map pipeline service status to job state
        if result.decision == "ALLOW":
            self.state = JobState.READY
        elif result.status.value == "FAILED":
            self.state = JobState.FAILED
            self.error_message = result.message
        else:
            self.state = JobState.BLOCKED
            self.error_message = result.message

    def mark_failed(self, error: str) -> None:
        self.state = JobState.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow().isoformat() + "Z"

    def mark_cancelled(self) -> None:
        self.state = JobState.CANCELLED
        self.completed_at = datetime.utcnow().isoformat() + "Z"
