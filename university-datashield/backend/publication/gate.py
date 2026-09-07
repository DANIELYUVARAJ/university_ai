# backend/publication/gate.py
"""
Publication Gate Decision Engine for Phase 5.
Enforces multi-layer safety checks:
  1. Role-based authorization check
  2. Mandatory masking policy compliance
  3. Unprotected sensitive field inspection
Implements strict DEFAULT DENY security semantics.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any

from access.access_engine import AccessEngine
from access.permissions import Permission
from policies.policy_engine import PolicyEngine
from policies.schemas import (
    PolicyValidationRequest,
    ValidationStatus,
    ProtectionAction,
)
from .schemas import (
    PublicationDecision,
    PublicationStatus,
    PublicationCheckRequest,
    PublicationCheckResponse,
    FieldPublicationDetail,
    PublishExecutionRequest,
    PublishExecutionResponse,
)


class PublicationGate:
    def __init__(self, policy_engine: PolicyEngine | None = None):
        self.policy_engine = policy_engine or PolicyEngine()
        self.access_engine = AccessEngine

    def evaluate(self, request: PublicationCheckRequest) -> PublicationCheckResponse:
        """
        Evaluate dataset against role authorization and masking policies.
        Default Deny principle: Any unauthorized role or policy violation results in BLOCK.
        """
        role_str = request.role.strip().upper()

        # ── 1. Role Authorization Check (Default Deny) ────────────────────────
        is_authorized = self.access_engine.can_perform(role_str, Permission.PUBLISH)

        # ── 2. Policy Validation Check ───────────────────────────────────────
        val_request = PolicyValidationRequest(
            dataset_name=request.dataset_name,
            fields=request.fields,
        )
        val_response = self.policy_engine.validate_dataset(val_request)

        # Check for policy violations, review-required fields, or missing policies on sensitive fields (Fail Closed)
        violations: List[Dict[str, Any]] = []
        for r in val_response.field_results:
            is_sensitive = (r.classification.upper() not in ("NON_SENSITIVE", "ACADEMIC_DATA", "PLACEMENT_DATA"))
            # Fail closed: sensitive field with missing or undefined masking policy must not publish
            if is_sensitive and r.required_action == ProtectionAction.NONE:
                violations.append({
                    "field": r.field,
                    "reason": f"Missing masking policy for sensitive field '{r.field}' (classification: {r.classification}); fail-closed security gate blocks publication"
                })
            elif r.status in (ValidationStatus.FAIL, ValidationStatus.REVIEW):
                violations.append({
                    "field": r.field,
                    "reason": f"Required {r.required_action.value} protection is missing (actual: {r.actual_action.value})"
                })

        is_policy_compliant = len(violations) == 0

        # Build detailed field summaries for UI inspection
        field_details: List[FieldPublicationDetail] = [
            FieldPublicationDetail(
                field=r.field,
                classification=r.classification,
                required_action=r.required_action,
                actual_action=r.actual_action,
                status="FAIL" if (r.classification.upper() not in ("NON_SENSITIVE", "ACADEMIC_DATA", "PLACEMENT_DATA") and r.required_action == ProtectionAction.NONE) else r.status.value,
                passed=(r.status == ValidationStatus.PASS and not (r.classification.upper() not in ("NON_SENSITIVE", "ACADEMIC_DATA", "PLACEMENT_DATA") and r.required_action == ProtectionAction.NONE)),
                reason=r.reason,
            )
            for r in val_response.field_results
        ]

        # ── 3. Decision Synthesis ─────────────────────────────────────────────
        reasons: List[Any] = []

        if not is_authorized:
            decision = PublicationDecision.BLOCK
            status = PublicationStatus.UNAUTHORIZED
            reasons.append(f"Role {role_str} is not authorized to publish this dataset")
            if not is_policy_compliant:
                reasons.extend(violations)

        elif not is_policy_compliant:
            decision = PublicationDecision.BLOCK
            status = PublicationStatus.PUBLICATION_BLOCKED
            reasons.extend(violations)

        else:
            # Everything is compliant and role is authorized
            decision = PublicationDecision.ALLOW
            status = PublicationStatus.SAFE_TO_PUBLISH

        return PublicationCheckResponse(
            decision=decision,
            authorized=is_authorized,
            policy_compliant=is_policy_compliant,
            status=status,
            dataset_name=request.dataset_name,
            role=role_str,
            policy_version=val_response.policy_version,
            reasons=reasons,
            field_details=field_details,
        )

    def execute_publish(self, request: PublishExecutionRequest) -> PublishExecutionResponse:
        """
        Simulate publication after independent backend verification.
        CRITICAL: Never trusts client-side flags; re-validates the entire publication gate.
        """
        # Independently re-run publication check
        check_request = PublicationCheckRequest(
            dataset_name=request.dataset_name,
            role=request.role,
            fields=request.fields,
        )
        check_result = self.evaluate(check_request)

        simulated_at = datetime.utcnow().isoformat() + "Z"

        if check_result.decision == PublicationDecision.ALLOW:
            return PublishExecutionResponse(
                success=True,
                decision=PublicationDecision.ALLOW,
                status=PublicationStatus.SAFE_TO_PUBLISH,
                message=(
                    f"Analytics Publication Simulated successfully to "
                    f"'{request.target_destination}'. Dataset is fully protected and compliant."
                ),
                dataset_name=request.dataset_name,
                role=check_result.role,
                reasons=[],
                simulated_at=simulated_at,
                is_simulation=True,
            )
        else:
            return PublishExecutionResponse(
                success=False,
                decision=PublicationDecision.BLOCK,
                status=check_result.status,
                message=(
                    f"Dataset publication BLOCKED by security gate. "
                    f"Dataset was NOT published to '{request.target_destination}'."
                ),
                dataset_name=request.dataset_name,
                role=check_result.role,
                reasons=check_result.reasons,
                simulated_at=simulated_at,
                is_simulation=True,
            )
