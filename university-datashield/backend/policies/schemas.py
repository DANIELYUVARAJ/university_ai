# backend/policies/schemas.py
"""
Data schemas for Phase 4 Masking Policy Engine.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProtectionAction(str, Enum):
    NONE = "NONE"
    MASK = "MASK"
    HASH = "HASH"
    GENERALIZE = "GENERALIZE"
    SUPPRESS = "SUPPRESS"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class PolicyRule(BaseModel):
    policy_id: str
    policy_version: str = "v1.0"
    target: str  # Classification name or specific field name
    is_field_override: bool = False
    required_action: ProtectionAction
    description: Optional[str] = None
    enabled: bool = True
    created_at: Optional[str] = None


class FieldValidationInput(BaseModel):
    name: str
    classification: Optional[str] = None
    actual_action: ProtectionAction = ProtectionAction.NONE
    sample_value: Optional[str] = None


class FieldValidationResult(BaseModel):
    field: str
    classification: str
    required_action: ProtectionAction
    actual_action: ProtectionAction
    status: ValidationStatus
    reason: str
    is_field_override: bool = False
    masked_preview: Optional[str] = None


class PolicyValidationRequest(BaseModel):
    fields: List[FieldValidationInput]
    dataset_name: Optional[str] = "validation_dataset"


class PolicyValidationSummary(BaseModel):
    total_evaluated: int
    protected_count: int
    unprotected_count: int
    violations: int
    review_required: int
    overall_compliance: float  # 0.0 to 100.0


class PolicyValidationResponse(BaseModel):
    policy_version: str = "v1.0"
    overall_status: ValidationStatus
    summary: PolicyValidationSummary
    field_results: List[FieldValidationResult]


class MaskingPreviewRequest(BaseModel):
    field_name: str
    action: ProtectionAction
    value: str
    data_type: Optional[str] = "string"


class MaskingPreviewResponse(BaseModel):
    field_name: str
    action: ProtectionAction
    original_present: bool = True
    masked_value: str
    is_synthetic: bool = True
