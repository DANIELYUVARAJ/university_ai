# backend/publication/schemas.py
"""
Data schemas for Phase 5 Publication Gate.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Any, Union, Dict
from pydantic import BaseModel

from policies.schemas import FieldValidationInput, ProtectionAction


class PublicationDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class PublicationStatus(str, Enum):
    SAFE_TO_PUBLISH = "SAFE_TO_PUBLISH"
    PUBLICATION_BLOCKED = "PUBLICATION_BLOCKED"
    UNAUTHORIZED = "UNAUTHORIZED"


class PublicationCheckRequest(BaseModel):
    dataset_name: str = "university_demo"
    role: str
    fields: List[FieldValidationInput]


class ReasonDetail(BaseModel):
    field: Optional[str] = None
    reason: str


class FieldPublicationDetail(BaseModel):
    field: str
    classification: str
    required_action: ProtectionAction
    actual_action: ProtectionAction
    status: str
    passed: bool
    reason: str


class PublicationCheckResponse(BaseModel):
    decision: PublicationDecision
    authorized: bool
    policy_compliant: bool
    status: PublicationStatus
    dataset_name: str
    role: str
    policy_version: str = "v1.0"
    reasons: List[Union[Dict[str, Any], str]]
    field_details: Optional[List[FieldPublicationDetail]] = None


class PublishExecutionRequest(BaseModel):
    dataset_name: str = "university_demo"
    role: str
    fields: List[FieldValidationInput]
    target_destination: Optional[str] = "Institutional Research Portal"


class PublishExecutionResponse(BaseModel):
    success: bool
    decision: PublicationDecision
    status: PublicationStatus
    message: str
    dataset_name: str
    role: str
    reasons: List[Union[Dict[str, Any], str]]
    simulated_at: str
    is_simulation: bool = True
