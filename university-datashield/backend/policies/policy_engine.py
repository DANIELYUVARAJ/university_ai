# backend/policies/policy_engine.py
"""
Core Policy Engine for Phase 4.
Evaluates fields against masking policies, determines required protection actions,
validates actual protection states, and generates PASS / FAIL / REVIEW outcomes.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from detection.detector import scan_field
from detection.schemas import FieldInput
from .schemas import (
    ProtectionAction,
    ValidationStatus,
    PolicyRule,
    FieldValidationInput,
    FieldValidationResult,
    PolicyValidationRequest,
    PolicyValidationResponse,
    PolicyValidationSummary,
)
from .default_policies import (
    POLICY_VERSION,
    CLASSIFICATION_DEFAULT_POLICIES,
    FIELD_SPECIFIC_OVERRIDES,
    get_default_policy_rules,
)
from .masking import apply_masking


class PolicyEngine:
    def __init__(
        self,
        version: str = POLICY_VERSION,
        classification_policies: Optional[Dict[str, ProtectionAction]] = None,
        field_overrides: Optional[Dict[str, ProtectionAction]] = None,
    ):
        self.version = version
        self.classification_policies = (
            dict(classification_policies)
            if classification_policies is not None
            else dict(CLASSIFICATION_DEFAULT_POLICIES)
        )
        self.field_overrides = (
            dict(field_overrides)
            if field_overrides is not None
            else dict(FIELD_SPECIFIC_OVERRIDES)
        )
        self.disabled_policies: set[str] = set()

    @classmethod
    async def load_active(cls) -> PolicyEngine:
        """Load engine configured with the currently active version from the governance layer."""
        from governance.governance_repository import GovernanceRepository
        try:
            active_ver = await GovernanceRepository.get_active_version()
            return cls(
                version=active_ver.version,
                classification_policies=dict(active_ver.policy_snapshot.classification_defaults),
                field_overrides=dict(active_ver.policy_snapshot.field_overrides),
            )
        except Exception:
            return cls()

    def get_required_action(
        self,
        field_name: str,
        classification: str
    ) -> Tuple[ProtectionAction, bool, str]:
        """
        Determine required protection action.
        Field-specific overrides take strict precedence over classification defaults.
        Returns: (action, is_field_override, rule_id)
        """
        clean_name = field_name.lower().strip()
        
        # 1. Check field-specific override
        if clean_name in self.field_overrides:
            rule_id = f"POL-FLD-{clean_name}"
            if rule_id not in self.disabled_policies:
                return self.field_overrides[clean_name], True, rule_id

        # 2. Check classification default
        clean_class = classification.upper().strip()
        rule_id = f"POL-CLS-{clean_class}"
        if rule_id in self.disabled_policies:
            return ProtectionAction.NONE, False, rule_id

        action = self.classification_policies.get(clean_class, ProtectionAction.NONE)
        return action, False, rule_id

    def validate_field(self, item: FieldValidationInput) -> FieldValidationResult:
        """
        Evaluate a single field against active policies and validate actual protection.
        """
        field_name = item.name.strip()

        # Resolve classification (auto-detect if missing)
        classification = item.classification
        if not classification:
            detected = scan_field(
                FieldInput(name=field_name, data_type="string", sample_pattern=item.sample_value or "")
            )
            classification = detected.classification
        else:
            classification = classification.upper().strip()

        # Determine required protection action
        required_action, is_override, _ = self.get_required_action(field_name, classification)
        actual_action = item.actual_action or ProtectionAction.NONE

        # Generate masked preview if synthetic sample value is provided
        preview = None
        if item.sample_value:
            preview = apply_masking(item.sample_value, actual_action, field_name=field_name)

        # Validation Decision Logic
        status: ValidationStatus
        reason: str

        if required_action == actual_action:
            status = ValidationStatus.PASS
            if required_action == ProtectionAction.NONE:
                reason = "No protection required for non-sensitive field"
            else:
                target_desc = f"Field override ({field_name})" if is_override else f"{classification.replace('_', ' ').title()}"
                reason = f"Required {required_action.value} policy for {target_desc} is satisfied"

        elif required_action != ProtectionAction.NONE and actual_action == ProtectionAction.NONE:
            status = ValidationStatus.FAIL
            target_desc = f"Field override ({field_name})" if is_override else f"{classification.replace('_', ' ').title()}"
            reason = f"{target_desc} requires {required_action.value}, but field is unprotected"

        elif required_action == ProtectionAction.NONE and actual_action != ProtectionAction.NONE:
            status = ValidationStatus.REVIEW
            reason = f"Field does not require protection, but {actual_action.value} was applied"

        else:
            # Both actions are protective but mismatch (e.g. required GENERALIZE, actual MASK)
            status = ValidationStatus.REVIEW
            reason = f"Protection mismatch: Required {required_action.value}, but actual is {actual_action.value}; review recommended"

        return FieldValidationResult(
            field=field_name,
            classification=classification,
            required_action=required_action,
            actual_action=actual_action,
            status=status,
            reason=reason,
            is_field_override=is_override,
            masked_preview=preview,
        )

    def validate_dataset(self, request: PolicyValidationRequest) -> PolicyValidationResponse:
        """
        Validate multiple fields, computing compliance summary statistics.
        """
        field_results: List[FieldValidationResult] = [
            self.validate_field(f) for f in request.fields
        ]

        total = len(field_results)
        violations = sum(1 for r in field_results if r.status == ValidationStatus.FAIL)
        reviews = sum(1 for r in field_results if r.status == ValidationStatus.REVIEW)
        passes = sum(1 for r in field_results if r.status == ValidationStatus.PASS)

        protected_count = sum(
            1 for r in field_results if r.actual_action != ProtectionAction.NONE
        )
        unprotected_count = total - protected_count

        compliance = round((passes / total) * 100, 1) if total > 0 else 100.0

        if violations > 0:
            overall_status = ValidationStatus.FAIL
        elif reviews > 0:
            overall_status = ValidationStatus.REVIEW
        else:
            overall_status = ValidationStatus.PASS

        summary = PolicyValidationSummary(
            total_evaluated=total,
            protected_count=protected_count,
            unprotected_count=unprotected_count,
            violations=violations,
            review_required=reviews,
            overall_compliance=compliance,
        )

        return PolicyValidationResponse(
            policy_version=self.version,
            overall_status=overall_status,
            summary=summary,
            field_results=field_results,
        )

    def get_active_policies(self) -> Dict:
        """Return structured configuration of all active policies."""
        return {
            "version": self.version,
            "policy_version": self.version,
            "classification_defaults": {
                k: v.value for k, v in self.classification_policies.items()
            },
            "field_overrides": {
                k: v.value for k, v in self.field_overrides.items()
            },
            "rules": [r.model_dump() for r in get_default_policy_rules()],
        }
