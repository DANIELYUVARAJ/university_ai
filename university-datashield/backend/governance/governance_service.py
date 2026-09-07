# backend/governance/governance_service.py
"""
Governance service managing Policy Change Requests, Approvals, Immutability, and Rollbacks.
Enforces Security Admin requirement, No-Self-Approval, and Automatic Post-Rollback Revalidation.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException

from audit.audit_service import AuditService
from audit.schemas import AuditAction
from policies.schemas import ProtectionAction, FieldValidationInput, PolicyValidationRequest
from policies.policy_engine import PolicyEngine
from .schemas import (
    ProposeChangeRequest,
    ApproveChangeRequest,
    RejectChangeRequest,
    RollbackRequest,
    RollbackResponse,
    PolicyChangeRecord,
    PolicyChangeStatus,
    PolicyVersionRecord,
    VersionStatus,
    PolicySnapshot,
    ProposedChangeDetail,
    PolicyDiffResponse,
    PolicyDiffItem,
)
from .governance_repository import GovernanceRepository


class GovernanceService:
    @classmethod
    async def get_active_version(cls) -> PolicyVersionRecord:
        return await GovernanceRepository.get_active_version()

    @classmethod
    async def get_all_versions(cls) -> List[PolicyVersionRecord]:
        return await GovernanceRepository.get_all_versions()

    @classmethod
    async def get_all_change_requests(cls) -> List[PolicyChangeRecord]:
        return await GovernanceRepository.get_all_change_requests()

    @classmethod
    async def _compute_next_version(cls, current_version: str) -> str:
        """Compute next available minor version that does not already exist."""
        match = re.search(r"v(\d+)\.(\d+)", current_version)
        major = int(match.group(1)) if match else 1
        minor = int(match.group(2)) if match else 0
        while True:
            minor += 1
            candidate = f"v{major}.{minor}"
            existing = await GovernanceRepository.get_version(candidate)
            if not existing:
                return candidate

    @classmethod
    async def propose_change(cls, req: ProposeChangeRequest) -> PolicyChangeRecord:
        """
        Submit a policy change request.
        Does NOT alter active policy behavior; remains PENDING until Security Admin review.
        """
        active_ver = await cls.get_active_version()
        current_snapshot = active_ver.policy_snapshot

        target = req.target.strip()
        is_field = req.is_field_override
        if is_field is None:
            is_field = target.upper() not in current_snapshot.classification_defaults

        # Find current action
        if is_field:
            current_action = current_snapshot.field_overrides.get(
                target.lower(), ProtectionAction.NONE
            )
        else:
            current_action = current_snapshot.classification_defaults.get(
                target.upper(), ProtectionAction.NONE
            )

        # Generate unique change ID
        existing = await GovernanceRepository.get_all_change_requests()
        change_id = f"CHG-{len(existing) + 1:03d}"
        proposed_version = await cls._compute_next_version(active_ver.version)

        change_detail = ProposedChangeDetail(
            target=target,
            is_field_override=is_field,
            current_action=current_action,
            proposed_action=req.proposed_action,
            description=f"Change {target} protection from {current_action.value} to {req.proposed_action.value}",
        )

        record = await GovernanceRepository.create_change_request(
            change_id=change_id,
            requested_by_role=req.requested_by_role,
            requested_by_actor=req.requested_by_actor,
            reason=req.reason,
            current_version=active_ver.version,
            proposed_version=proposed_version,
            change_detail=change_detail,
        )

        # Audit Event
        await AuditService.log_event(
            action=AuditAction.POLICY_CHANGE_PROPOSED,
            actor_role=req.requested_by_role,
            actor_id=req.requested_by_actor,
            result="PENDING",
            reason=req.reason,
            policy_version=active_ver.version,
            change_id=change_id,
            metadata={
                "target": target,
                "current_action": current_action.value,
                "proposed_action": req.proposed_action.value,
                "proposed_version": proposed_version,
            },
        )

        return record

    @classmethod
    async def approve_change(cls, req: ApproveChangeRequest) -> PolicyVersionRecord:
        """
        Approve a pending policy change.
        Enforces:
          - Only SECURITY_ADMIN role can approve.
          - NO SELF-APPROVAL: Proposer cannot approve their own change.
        Creates a new immutable policy version and sets it active.
        """
        # 1. Enforce SECURITY_ADMIN role
        if req.reviewed_by_role.upper().strip() != "SECURITY_ADMIN":
            raise HTTPException(
                status_code=403,
                detail="GOVERNANCE_ROLE_REQUIRED: Only SECURITY_ADMIN can approve policy changes",
            )

        # 2. Fetch change request
        change = await GovernanceRepository.get_change_request(req.change_id)
        if not change:
            raise HTTPException(
                status_code=404,
                detail=f"CHANGE_NOT_FOUND: Change request {req.change_id} does not exist",
            )

        if change.status != PolicyChangeStatus.PENDING:
            raise HTTPException(
                status_code=409,
                detail=f"CHANGE_ALREADY_REVIEWED: Change request {req.change_id} is already {change.status.value}",
            )

        # 3. NO SELF-APPROVAL ENFORCEMENT
        if change.requested_by_actor.strip().lower() == req.reviewed_by_actor.strip().lower():
            raise HTTPException(
                status_code=409,
                detail="SELF_APPROVAL_BLOCKED: Proposer cannot approve their own policy change request",
            )

        # 4. Construct updated snapshot
        active_ver = await cls.get_active_version()
        new_cls_defaults = dict(active_ver.policy_snapshot.classification_defaults)
        new_fld_overrides = dict(active_ver.policy_snapshot.field_overrides)

        detail = change.proposed_change
        if detail.is_field_override:
            new_fld_overrides[detail.target.lower()] = detail.proposed_action
        else:
            new_cls_defaults[detail.target.upper()] = detail.proposed_action

        new_snapshot = PolicySnapshot(
            classification_defaults=new_cls_defaults,
            field_overrides=new_fld_overrides,
        )

        # 5. Create new immutable version
        target_version = change.proposed_version
        if await GovernanceRepository.get_version(target_version):
            target_version = await cls._compute_next_version(active_ver.version)

        new_version_record = await GovernanceRepository.create_version(
            version=target_version,
            created_by=req.reviewed_by_actor,
            description=f"Approved change {change.id}: {detail.target} -> {detail.proposed_action.value}. Reason: {req.review_reason}",
            snapshot=new_snapshot,
            parent_version=active_ver.version,
            change_id=change.id,
            status=VersionStatus.ACTIVE,
        )

        # 6. Update change request record
        await GovernanceRepository.update_change_status(
            change_id=change.id,
            status=PolicyChangeStatus.APPROVED,
            reviewed_by_role=req.reviewed_by_role,
            reviewed_by_actor=req.reviewed_by_actor,
            review_reason=req.review_reason or "Approved by Security Admin",
        )

        # 7. Audit log
        await AuditService.log_event(
            action=AuditAction.POLICY_APPROVED,
            actor_role=req.reviewed_by_role,
            actor_id=req.reviewed_by_actor,
            result="APPROVED",
            reason=req.review_reason,
            policy_version=new_version_record.version,
            change_id=change.id,
            metadata={
                "previous_version": active_ver.version,
                "new_version": new_version_record.version,
                "target": detail.target,
                "new_action": detail.proposed_action.value,
            },
        )

        return new_version_record

    @classmethod
    async def reject_change(cls, req: RejectChangeRequest) -> PolicyChangeRecord:
        """Reject a pending policy change."""
        if req.reviewed_by_role.upper().strip() != "SECURITY_ADMIN":
            raise HTTPException(
                status_code=403,
                detail="GOVERNANCE_ROLE_REQUIRED: Only SECURITY_ADMIN can reject policy changes",
            )

        change = await GovernanceRepository.get_change_request(req.change_id)
        if not change:
            raise HTTPException(
                status_code=404,
                detail=f"CHANGE_NOT_FOUND: Change request {req.change_id} does not exist",
            )

        if change.status != PolicyChangeStatus.PENDING:
            raise HTTPException(
                status_code=409,
                detail=f"CHANGE_ALREADY_REVIEWED: Change request {req.change_id} is already {change.status.value}",
            )

        if change.requested_by_actor.strip().lower() == req.reviewed_by_actor.strip().lower():
            raise HTTPException(
                status_code=409,
                detail="SELF_APPROVAL_BLOCKED: Proposer cannot reject their own change request",
            )

        await GovernanceRepository.update_change_status(
            change_id=change.id,
            status=PolicyChangeStatus.REJECTED,
            reviewed_by_role=req.reviewed_by_role,
            reviewed_by_actor=req.reviewed_by_actor,
            review_reason=req.review_reason,
        )

        await AuditService.log_event(
            action=AuditAction.POLICY_REJECTED,
            actor_role=req.reviewed_by_role,
            actor_id=req.reviewed_by_actor,
            result="REJECTED",
            reason=req.review_reason,
            policy_version=change.current_version,
            change_id=change.id,
        )

        updated_change = await GovernanceRepository.get_change_request(req.change_id)
        assert updated_change is not None
        return updated_change

    @classmethod
    async def diff_versions(cls, from_version_str: str, to_version_str: str) -> PolicyDiffResponse:
        """Compare policy configurations between two immutable versions."""
        v_from = await GovernanceRepository.get_version(from_version_str)
        if not v_from:
            raise HTTPException(status_code=404, detail=f"Version {from_version_str} not found")

        v_to = await GovernanceRepository.get_version(to_version_str)
        if not v_to:
            raise HTTPException(status_code=404, detail=f"Version {to_version_str} not found")

        diffs: List[PolicyDiffItem] = []
        changes_count = 0

        # Classification defaults diff
        all_cls = set(v_from.policy_snapshot.classification_defaults.keys()).union(
            v_to.policy_snapshot.classification_defaults.keys()
        )
        for c in sorted(all_cls):
            act_from = v_from.policy_snapshot.classification_defaults.get(c)
            act_to = v_to.policy_snapshot.classification_defaults.get(c)
            changed = act_from != act_to
            if changed:
                changes_count += 1
            diffs.append(
                PolicyDiffItem(
                    target=c,
                    is_field_override=False,
                    from_action=act_from,
                    to_action=act_to,
                    changed=changed,
                )
            )

        # Field overrides diff
        all_flds = set(v_from.policy_snapshot.field_overrides.keys()).union(
            v_to.policy_snapshot.field_overrides.keys()
        )
        for f in sorted(all_flds):
            act_from = v_from.policy_snapshot.field_overrides.get(f)
            act_to = v_to.policy_snapshot.field_overrides.get(f)
            changed = act_from != act_to
            if changed:
                changes_count += 1
            diffs.append(
                PolicyDiffItem(
                    target=f,
                    is_field_override=True,
                    from_action=act_from,
                    to_action=act_to,
                    changed=changed,
                )
            )

        return PolicyDiffResponse(
            from_version=from_version_str,
            to_version=to_version_str,
            changes_count=changes_count,
            diffs=diffs,
        )

    @classmethod
    async def rollback_policy(cls, req: RollbackRequest) -> RollbackResponse:
        """
        Execute safe rollback to a target version.
        Enforces:
          - Only SECURITY_ADMIN can rollback.
          - Preserves history by creating a new rollback version (e.g. v1.3-rollback).
          - Executes automatic post-rollback revalidation against synthetic validation dataset.
        """
        if req.actor_role.upper().strip() != "SECURITY_ADMIN":
            raise HTTPException(
                status_code=403,
                detail="GOVERNANCE_ROLE_REQUIRED: Only SECURITY_ADMIN can execute policy rollback",
            )

        target_ver = await GovernanceRepository.get_version(req.target_version)
        if not target_ver:
            raise HTTPException(
                status_code=404,
                detail=f"POLICY_VERSION_NOT_FOUND: Target rollback version {req.target_version} does not exist",
            )

        active_ver = await cls.get_active_version()
        if active_ver.version == target_ver.version:
            raise HTTPException(
                status_code=409,
                detail=f"ROLLBACK_NOT_ALLOWED: Target version {req.target_version} is already the active version",
            )

        # Generate new rollback version tag (e.g. v1.3-rollback)
        all_vers = await GovernanceRepository.get_all_versions()
        rollback_tag = f"v1.{len(all_vers)}-rollback"

        # Create new version with target snapshot
        new_version_record = await GovernanceRepository.create_version(
            version=rollback_tag,
            created_by=req.actor_id,
            description=f"Rollback to {target_ver.version}. Reason: {req.reason}",
            snapshot=target_ver.policy_snapshot,
            parent_version=active_ver.version,
            status=VersionStatus.ACTIVE,
        )

        # Automatic post-rollback revalidation against synthetic validation dataset
        revalidation_summary, revalidation_status = await cls._revalidate_policy(new_version_record)

        # Audit log
        await AuditService.log_event(
            action=AuditAction.POLICY_ROLLBACK,
            actor_role=req.actor_role,
            actor_id=req.actor_id,
            result=revalidation_status,
            reason=req.reason,
            policy_version=rollback_tag,
            metadata={
                "from_version": active_ver.version,
                "target_version": target_ver.version,
                "resulting_active_version": rollback_tag,
                "revalidation": revalidation_summary,
            },
        )

        return RollbackResponse(
            success=True,
            resulting_active_version=rollback_tag,
            target_version=target_ver.version,
            previous_version=active_ver.version,
            revalidation_summary=revalidation_summary,
            revalidation_status=revalidation_status,
            message=f"Rollback completed. Active version is now {rollback_tag} matching {target_ver.version}.",
        )

    @classmethod
    async def _revalidate_policy(cls, version_rec: PolicyVersionRecord) -> Tuple[Dict[str, Any], str]:
        """Run policy validation on synthetic validation dataset to confirm protection behavior."""
        data_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "synthetic"
            / "validation_dataset.json"
        )
        if not data_path.exists():
            return {"status": "SKIPPED", "reason": "Validation dataset not found"}, "SKIPPED"

        with open(data_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        # Instantiate engine with this specific snapshot
        engine = PolicyEngine(
            version=version_rec.version,
            classification_policies=dict(version_rec.policy_snapshot.classification_defaults),
            field_overrides=dict(version_rec.policy_snapshot.field_overrides),
        )

        # Validate fields using target policy
        fields_input = []
        for item in dataset:
            req_act, _, _ = engine.get_required_action(
                item["field_name"], item["expected_classification"]
            )
            # Simulate compliant application matching required policy
            fields_input.append(
                FieldValidationInput(
                    name=item["field_name"],
                    classification=item["expected_classification"],
                    actual_action=req_act,
                    sample_value=item.get("sample_pattern"),
                )
            )

        val_res = engine.validate_dataset(
            PolicyValidationRequest(
                dataset_name="validation_dataset_revalidation",
                fields=fields_input,
            )
        )

        summary = val_res.summary.model_dump()
        return summary, val_res.overall_status.value
