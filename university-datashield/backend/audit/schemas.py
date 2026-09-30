# backend/audit/schemas.py
"""
Data schemas for Phase 6 Audit Trail subsystem.
Zero PII guarantee: raw personal data is never captured.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    SCAN = "SCAN"
    POLICY_VALIDATION = "POLICY_VALIDATION"
    PUBLICATION_CHECK = "PUBLICATION_CHECK"
    PUBLICATION = "PUBLICATION"
    ACCESS_DENIAL = "ACCESS_DENIAL"
    POLICY_CHANGE_PROPOSED = "POLICY_CHANGE_PROPOSED"
    POLICY_APPROVED = "POLICY_APPROVED"
    POLICY_REJECTED = "POLICY_REJECTED"
    POLICY_ROLLBACK = "POLICY_ROLLBACK"
    # Phase 10: Analytical Pipeline Actions
    PIPELINE_CREATED = "PIPELINE_CREATED"
    PIPELINE_SCAN = "PIPELINE_SCAN"
    PIPELINE_VALIDATION = "PIPELINE_VALIDATION"
    PIPELINE_BLOCKED = "PIPELINE_BLOCKED"
    PIPELINE_READY = "PIPELINE_READY"
    PIPELINE_PUBLISHED = "PIPELINE_PUBLISHED"
    PIPELINE_FAILED = "PIPELINE_FAILED"


class AuditEventInput(BaseModel):
    action: AuditAction
    actor_role: str
    actor_id: Optional[str] = "system"
    dataset: Optional[str] = None
    field_name: Optional[str] = None
    result: str  # e.g. "ALLOW", "BLOCK", "PASS", "FAIL", "SUCCESS"
    reason: Optional[str] = None
    policy_version: Optional[str] = "v1.0"
    change_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class AuditEventRecord(BaseModel):
    id: int
    timestamp: str
    actor_role: str
    actor_id: str
    action: AuditAction
    dataset: Optional[str] = None
    field_name: Optional[str] = None
    result: str
    reason: Optional[str] = None
    policy_version: Optional[str] = None
    change_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    previous_hash: str
    event_hash: str


class AuditFilterParams(BaseModel):
    action: Optional[AuditAction] = None
    actor_role: Optional[str] = None
    result: Optional[str] = None
    policy_version: Optional[str] = None
    dataset: Optional[str] = None
    limit: int = 100


class AuditIntegrityResponse(BaseModel):
    status: str  # "VALID" or "COMPROMISED"
    events_checked: int
    head_hash: Optional[str] = None
    details: str
