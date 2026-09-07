# backend/governance/schemas.py
"""
Data schemas for Phase 6 Policy Versioning, Change Approval Workflow, and Rollback.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from policies.schemas import ProtectionAction, PolicyValidationResponse


class PolicyChangeStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class VersionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ROLLED_BACK = "ROLLED_BACK"


class PolicySnapshot(BaseModel):
    classification_defaults: Dict[str, ProtectionAction]
    field_overrides: Dict[str, ProtectionAction]


class ProposedChangeDetail(BaseModel):
    target: str  # Field name or classification category
    is_field_override: bool = True
    current_action: ProtectionAction
    proposed_action: ProtectionAction
    description: Optional[str] = None


class ProposeChangeRequest(BaseModel):
    requested_by_role: str
    requested_by_actor: str = "engineer-demo"
    target: str
    proposed_action: ProtectionAction
    reason: str
    is_field_override: Optional[bool] = None


class ApproveChangeRequest(BaseModel):
    change_id: str
    reviewed_by_role: str
    reviewed_by_actor: str = "security-admin-demo"
    review_reason: Optional[str] = "Approved following institutional data governance review"


class RejectChangeRequest(BaseModel):
    change_id: str
    reviewed_by_role: str
    reviewed_by_actor: str = "security-admin-demo"
    review_reason: str


class PolicyChangeRecord(BaseModel):
    id: str
    requested_at: str
    requested_by_role: str
    requested_by_actor: str
    reason: str
    current_version: str
    proposed_version: str
    proposed_change: ProposedChangeDetail
    status: PolicyChangeStatus
    reviewed_by_role: Optional[str] = None
    reviewed_by_actor: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_reason: Optional[str] = None


class PolicyVersionRecord(BaseModel):
    id: int
    version: str
    created_at: str
    created_by: str
    status: VersionStatus
    parent_version: Optional[str] = None
    change_id: Optional[str] = None
    description: str
    policy_snapshot: PolicySnapshot
    active: bool


class PolicyDiffItem(BaseModel):
    target: str
    is_field_override: bool
    from_action: Optional[ProtectionAction] = None
    to_action: Optional[ProtectionAction] = None
    changed: bool


class PolicyDiffResponse(BaseModel):
    from_version: str
    to_version: str
    changes_count: int
    diffs: List[PolicyDiffItem]


class RollbackRequest(BaseModel):
    target_version: str
    actor_role: str
    actor_id: str = "security-admin-demo"
    reason: str = "Rollback to previous approved baseline"


class RollbackResponse(BaseModel):
    success: bool
    resulting_active_version: str
    target_version: str
    previous_version: str
    revalidation_summary: Dict[str, Any]
    revalidation_status: str
    message: str
