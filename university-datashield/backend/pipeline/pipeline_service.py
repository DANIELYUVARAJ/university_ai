# backend/pipeline/pipeline_service.py
"""
University DataShield – Analytical Pipeline Integration Service (Phase 10).
Orchestrates end-to-end analytical pipeline security verification:
  1. Ingestion & Schema Extraction (safe parsing, zero raw PII persistence)
  2. Sensitive-Field Detection (reusing Phase 9 detector & intelligence)
  3. Masking Policy Validation (reusing active Policy Engine)
  4. Role Authorization (reusing AccessEngine / RBAC)
  5. Publication Gate (reusing PublicationGate with strict Fail-Closed semantics)
  6. Masking Previews (reusing deterministic masking engine)
  7. Audit Logging (reusing SHA-256 tamper-evident ledger)
  8. Idempotency & Safe Retry Semantics
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from detection.detector import scan_fields_with_risk
from detection.schemas import FieldInput, FieldResult, DatasetRiskSummary
from policies.policy_engine import PolicyEngine
from policies.schemas import (
    FieldValidationInput,
    PolicyValidationRequest,
    ProtectionAction,
    ValidationStatus,
)
from policies.masking import apply_masking
from access.access_engine import AccessEngine
from access.permissions import Permission
from publication.gate import PublicationGate
from publication.schemas import PublicationCheckRequest, PublicationDecision
from audit.audit_service import AuditService
from audit.schemas import AuditAction

from .schemas import (
    PipelineState,
    DatasetFormat,
    PipelineValidateRequest,
    PipelineValidateResponse,
    PipelinePublishRequest,
    PipelinePublishResponse,
    PipelineViolation,
    PipelineRecommendation,
    PipelineMaskingPreviewItem,
    PipelineBatchRequest,
    PipelineBatchResponse,
    BatchSummary,
    PipelineReportResponse,
)
from .ingestion import DatasetIngestionService
from .repository import PipelineRepository


def generate_pipeline_id() -> str:
    """Generate safe, non-PII pipeline execution identifier."""
    year = datetime.utcnow().year
    token = uuid.uuid4().hex[:6].upper()
    return f"PL-{year}-{token}"


def generate_execution_id() -> str:
    """Generate safe execution identifier."""
    year = datetime.utcnow().year
    token = uuid.uuid4().hex[:6].upper()
    return f"EX-{year}-{token}"


class PipelineService:
    @classmethod
    async def validate_pipeline(
        cls, request: PipelineValidateRequest
    ) -> PipelineValidateResponse:
        """
        Validate an analytical pipeline dataset through the complete DataShield security gate.
        Executes strict fail-closed sequence.
        """
        pipeline_id = request.pipeline_id or generate_pipeline_id()
        execution_id = request.execution_id or generate_execution_id()
        created_at = datetime.utcnow().isoformat() + "Z"
        role_str = request.role.strip().upper()

        # ── 0. Check Idempotency ──────────────────────────────────────────────
        if request.execution_id:
            existing_run = await PipelineRepository.get_by_execution_id(request.execution_id)
            if existing_run:
                # Idempotent response: return previously validated result
                summary = existing_run.get("summary", {})
                return PipelineValidateResponse(
                    pipeline_id=existing_run["pipeline_id"],
                    execution_id=existing_run["execution_id"],
                    dataset_name=existing_run["dataset_name"],
                    status=PipelineState(existing_run["status"]),
                    decision=existing_run["decision"],
                    detection_status=summary.get("detection_status", "PASS"),
                    policy_status=summary.get("policy_status", "PASS"),
                    authorization_status=summary.get("authorization_status", "PASS"),
                    risk_level=existing_run["risk_level"],
                    risk_score=existing_run["risk_score"],
                    sensitive_fields=summary.get("sensitive_fields", []),
                    policy_violations=[PipelineViolation(**v) for v in summary.get("policy_violations", [])],
                    recommended_actions=[PipelineRecommendation(**r) for r in summary.get("recommended_actions", [])],
                    masking_previews=[PipelineMaskingPreviewItem(**m) for m in summary.get("masking_previews", [])],
                    audit_reference=existing_run["audit_reference"],
                    policy_version=existing_run["policy_version"],
                    role=existing_run["role"],
                    target_destination=existing_run["target_destination"],
                    message="Idempotent response: returning previously recorded execution validation.",
                    created_at=existing_run["created_at"],
                    completed_at=existing_run["completed_at"],
                )

        # ── 1. Ingestion & Schema Extraction ──────────────────────────────────
        format_type = "CSV"
        field_inputs: List[FieldInput] = []
        validation_inputs: List[FieldValidationInput] = []

        try:
            if request.raw_content is not None and request.raw_content.strip():
                schema, field_inputs = DatasetIngestionService.ingest(
                    request.dataset_name,
                    request.raw_content,
                    request.format,
                )
                format_type = schema.format.value
                for f_info in schema.fields:
                    validation_inputs.append(
                        FieldValidationInput(
                            name=f_info.field_name,
                            actual_action=ProtectionAction.NONE,
                            sample_value=f_info.sample_value,
                        )
                    )
            elif request.fields is not None and len(request.fields) > 0:
                format_type = request.format.value if request.format else "SCHEMA"
                validation_inputs = request.fields
                for f in request.fields:
                    field_inputs.append(
                        FieldInput(
                            name=f.name,
                            data_type=getattr(f, "data_type", "string") or "string",
                            sample_pattern=f.sample_value or "",
                        )
                    )
            else:
                raise ValueError("No dataset content or field definitions provided for pipeline validation")

        except Exception as exc:
            # Ingestion or schema failure -> Fail closed to FAILED
            completed_at = datetime.utcnow().isoformat() + "Z"
            audit_ev = await AuditService.log_event(
                action=AuditAction.PIPELINE_FAILED,
                actor_role=role_str,
                dataset=request.dataset_name,
                result="FAIL",
                reason=f"Pipeline ingestion failed: {str(exc)}",
                metadata={"pipeline_id": pipeline_id, "execution_id": execution_id},
            )
            resp = PipelineValidateResponse(
                pipeline_id=pipeline_id,
                execution_id=execution_id,
                dataset_name=request.dataset_name,
                status=PipelineState.FAILED,
                decision="BLOCK",
                detection_status="FAIL",
                policy_status="FAIL",
                authorization_status="FAIL",
                risk_level="CRITICAL",
                risk_score=100,
                sensitive_fields=[],
                policy_violations=[
                    PipelineViolation(
                        field="dataset",
                        classification="CORRUPT_PAYLOAD",
                        required_action="VALID_DATASET",
                        actual_action="NONE",
                        reason=str(exc),
                    )
                ],
                recommended_actions=[],
                masking_previews=[],
                audit_reference=audit_ev.event_hash,
                policy_version="v1.0",
                role=role_str,
                target_destination=request.target_destination,
                message=f"Pipeline validation failed at ingestion stage: {str(exc)}",
                created_at=created_at,
                completed_at=completed_at,
            )
            await PipelineRepository.create_or_update_run(
                pipeline_id=pipeline_id,
                execution_id=execution_id,
                dataset_name=request.dataset_name,
                format_type=format_type,
                status=PipelineState.FAILED.value,
                risk_level="CRITICAL",
                risk_score=100,
                fields_count=0,
                sensitive_count=0,
                violations_count=1,
                decision="BLOCK",
                role=role_str,
                policy_version="v1.0",
                target_destination=request.target_destination,
                summary_dict=resp.model_dump(),
                report_markdown=cls._generate_markdown_report(resp),
                audit_reference=audit_ev.event_hash,
                completed_at=completed_at,
            )
            return resp

        # ── 2. Sensitive-Field Detection (SCANNING -> DETECTED) ───────────────
        detection_results, risk_summary = scan_fields_with_risk(field_inputs)
        sensitive_fields = [
            r.field for r in detection_results
            if r.classification.upper() not in ("NON_SENSITIVE", "ACADEMIC_DATA", "PLACEMENT_DATA")
        ]
        detection_status = "PASS"
        if any(r.ambiguity_status == "REVIEW" for r in detection_results):
            detection_status = "REVIEW"

        # ── 3. Policy Resolution (VALIDATING_POLICY) ──────────────────────────
        policy_engine = await PolicyEngine.load_active()

        # Synchronize validation inputs with detected classifications
        for v_input, d_result in zip(validation_inputs, detection_results):
            if not v_input.classification or v_input.classification.upper() not in policy_engine.classification_policies:
                v_input.classification = d_result.classification
            if not v_input.sample_value and d_result.recommendation:
                v_input.sample_value = d_result.normalized_name

        policy_val_req = PolicyValidationRequest(
            dataset_name=request.dataset_name,
            fields=validation_inputs,
        )
        policy_val_resp = policy_engine.validate_dataset(policy_val_req)

        violations: List[PipelineViolation] = []
        recommendations: List[PipelineRecommendation] = []
        masking_previews: List[PipelineMaskingPreviewItem] = []

        for f_res in policy_val_resp.field_results:
            is_sensitive = (
                f_res.classification.upper() not in ("NON_SENSITIVE", "ACADEMIC_DATA", "PLACEMENT_DATA")
            )
            # Fail closed on unprotected sensitive field or missing policy
            if is_sensitive and f_res.required_action == ProtectionAction.NONE:
                violations.append(
                    PipelineViolation(
                        field=f_res.field,
                        classification=f_res.classification,
                        required_action="PROTECTED",
                        actual_action=f_res.actual_action.value,
                        reason=f"Missing masking policy for sensitive field '{f_res.field}'",
                    )
                )
            elif f_res.status in (ValidationStatus.FAIL, ValidationStatus.REVIEW):
                violations.append(
                    PipelineViolation(
                        field=f_res.field,
                        classification=f_res.classification,
                        required_action=f_res.required_action.value,
                        actual_action=f_res.actual_action.value,
                        reason=f_res.reason,
                    )
                )

            # Generate masking recommendation & preview for sensitive fields
            if is_sensitive:
                sample_val = f_res.masked_preview or "DEMO_VAL_12345"
                if f_res.required_action != ProtectionAction.NONE:
                    preview_str = apply_masking(sample_val, f_res.required_action, field_name=f_res.field)
                else:
                    preview_str = "[BLOCKED - NO POLICY]"

                recommendations.append(
                    PipelineRecommendation(
                        field=f_res.field,
                        recommended_action=f_res.required_action.value,
                        reason=f"Field classified as {f_res.classification}; requires {f_res.required_action.value}",
                        preview=preview_str,
                    )
                )
                masking_previews.append(
                    PipelineMaskingPreviewItem(
                        field=f_res.field,
                        classification=f_res.classification,
                        required_policy=f_res.required_action.value,
                        original_sample_type=f_res.classification,
                        preview=preview_str,
                    )
                )

        policy_status = "PASS" if len(violations) == 0 else "FAIL"

        # ── 4. Role Authorization (VALIDATING_ACCESS) ─────────────────────────
        is_authorized = AccessEngine.can_perform(role_str, Permission.PUBLISH)
        auth_status = "PASS" if is_authorized else "FAIL"

        # ── 5. Publication Gate Decision (FAIL-CLOSED) ────────────────────────
        pub_gate = PublicationGate(policy_engine=policy_engine)
        pub_check = pub_gate.evaluate(
            PublicationCheckRequest(
                dataset_name=request.dataset_name,
                role=role_str,
                fields=validation_inputs,
            )
        )

        completed_at = datetime.utcnow().isoformat() + "Z"
        decision = "ALLOW" if pub_check.decision == PublicationDecision.ALLOW else "BLOCK"

        if decision == "ALLOW":
            state = PipelineState.READY
            action_to_log = AuditAction.PIPELINE_READY
            msg = f"Pipeline validation PASSED. Dataset '{request.dataset_name}' is SAFE to publish to {request.target_destination}."
        else:
            state = PipelineState.BLOCKED
            action_to_log = AuditAction.PIPELINE_BLOCKED
            reasons_summary = "; ".join(str(r) for r in pub_check.reasons[:3])
            msg = f"Pipeline BLOCKED by publication gate. Security violations detected: {reasons_summary}"

        # ── 6. Cryptographic Audit Event ──────────────────────────────────────
        audit_rec = await AuditService.log_event(
            action=action_to_log,
            actor_role=role_str,
            dataset=request.dataset_name,
            result=decision,
            reason=msg,
            policy_version=policy_engine.version,
            metadata={
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "violations_count": len(violations),
                "risk_score": risk_summary.risk_score,
                "risk_level": str(getattr(risk_summary.risk_level, "value", risk_summary.risk_level)),
            },
        )

        resp = PipelineValidateResponse(
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            dataset_name=request.dataset_name,
            status=state,
            decision=decision,
            detection_status=detection_status,
            policy_status=policy_status,
            authorization_status=auth_status,
            risk_level=str(getattr(risk_summary.risk_level, "value", risk_summary.risk_level)),
            risk_score=risk_summary.risk_score,
            sensitive_fields=sensitive_fields,
            policy_violations=violations,
            recommended_actions=recommendations,
            masking_previews=masking_previews,
            audit_reference=audit_rec.event_hash,
            policy_version=policy_engine.version,
            role=role_str,
            target_destination=request.target_destination,
            message=msg,
            created_at=created_at,
            completed_at=completed_at,
        )

        # ── 7. Persistence ────────────────────────────────────────────────────
        markdown_rep = cls._generate_markdown_report(resp)
        await PipelineRepository.create_or_update_run(
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            dataset_name=request.dataset_name,
            format_type=format_type,
            status=state.value,
            risk_level=resp.risk_level,
            risk_score=resp.risk_score,
            fields_count=len(field_inputs),
            sensitive_count=len(sensitive_fields),
            violations_count=len(violations),
            decision=decision,
            role=role_str,
            policy_version=policy_engine.version,
            target_destination=request.target_destination,
            summary_dict=resp.model_dump(),
            report_markdown=markdown_rep,
            audit_reference=audit_rec.event_hash,
            completed_at=completed_at,
        )

        return resp

    @classmethod
    async def publish_pipeline(
        cls, request: PipelinePublishRequest
    ) -> PipelinePublishResponse:
        """
        Publish an analytical pipeline dataset to target destination.
        CRITICAL SECURITY REQUIREMENT:
          Independently re-validates entire pipeline backend-side.
          Never trusts client-side 'client_approved=True' flags.
        """
        existing = await PipelineRepository.get_by_pipeline_id(request.pipeline_id)
        if not existing:
            return PipelinePublishResponse(
                pipeline_id=request.pipeline_id,
                execution_id=request.execution_id or generate_execution_id(),
                status=PipelineState.FAILED,
                decision="BLOCK",
                success=False,
                message=f"Pipeline '{request.pipeline_id}' not found.",
                target_destination=request.target_destination,
            )

        # Re-validate pipeline to ensure no state degradation or client-side bypass
        validate_req = PipelineValidateRequest(
            pipeline_id=request.pipeline_id,
            execution_id=request.execution_id or existing.get("execution_id"),
            dataset_name=existing["dataset_name"],
            raw_content=request.raw_content,
            format=request.format,
            fields=request.fields,
            role=request.role,
            target_destination=request.target_destination,
            client_approved=request.client_approved,  # Ignored by backend decision logic
        )
        val_result = await cls.validate_pipeline(validate_req)

        if val_result.decision != "ALLOW":
            # Security Gate Blocks Publication
            await AuditService.log_event(
                action=AuditAction.PIPELINE_BLOCKED,
                actor_role=request.role.upper().strip(),
                dataset=existing["dataset_name"],
                result="BLOCK",
                reason=f"Attempted publication of unapproved pipeline '{request.pipeline_id}' was BLOCKED.",
                policy_version=val_result.policy_version,
                metadata={"pipeline_id": request.pipeline_id},
            )
            return PipelinePublishResponse(
                pipeline_id=request.pipeline_id,
                execution_id=val_result.execution_id,
                status=PipelineState.BLOCKED,
                decision="BLOCK",
                success=False,
                message=(
                    f"Publication BLOCKED by DataShield Security Gate: "
                    f"Unmasked sensitive fields or insufficient role authorization."
                ),
                target_destination=request.target_destination,
                audit_reference=val_result.audit_reference,
                reasons=[v.reason for v in val_result.policy_violations],
            )

        # Publication Allowed
        published_at = datetime.utcnow().isoformat() + "Z"
        audit_ev = await AuditService.log_event(
            action=AuditAction.PIPELINE_PUBLISHED,
            actor_role=request.role.upper().strip(),
            dataset=existing["dataset_name"],
            result="ALLOW",
            reason=f"Pipeline '{request.pipeline_id}' successfully published to {request.target_destination}.",
            policy_version=val_result.policy_version,
            metadata={
                "pipeline_id": request.pipeline_id,
                "target_destination": request.target_destination,
            },
        )

        # Update status to PUBLISHED in repository
        summary = existing.get("summary", {})
        summary["status"] = PipelineState.PUBLISHED.value
        await PipelineRepository.create_or_update_run(
            pipeline_id=request.pipeline_id,
            execution_id=val_result.execution_id,
            dataset_name=existing["dataset_name"],
            format_type=existing["format"],
            status=PipelineState.PUBLISHED.value,
            risk_level=val_result.risk_level,
            risk_score=val_result.risk_score,
            fields_count=existing["fields_count"],
            sensitive_count=existing["sensitive_count"],
            violations_count=0,
            decision="ALLOW",
            role=request.role.upper().strip(),
            policy_version=val_result.policy_version,
            target_destination=request.target_destination,
            summary_dict=summary,
            audit_reference=audit_ev.event_hash,
            completed_at=published_at,
        )

        return PipelinePublishResponse(
            pipeline_id=request.pipeline_id,
            execution_id=val_result.execution_id,
            status=PipelineState.PUBLISHED,
            decision="ALLOW",
            success=True,
            message=f"Pipeline dataset successfully published to {request.target_destination}.",
            published_at=published_at,
            target_destination=request.target_destination,
            audit_reference=audit_ev.event_hash,
            reasons=[],
        )

    @classmethod
    async def batch_validate(
        cls, request: PipelineBatchRequest
    ) -> PipelineBatchResponse:
        """
        Validate multiple analytical datasets in a batch.
        Fail-Closed Principle: If ANY dataset is blocked or failed, the batch overall_decision is BLOCK.
        """
        results: List[PipelineValidateResponse] = []
        passed = 0
        blocked = 0
        failed = 0
        review_required = 0

        for item in request.datasets:
            v_req = PipelineValidateRequest(
                dataset_name=item.dataset_name,
                raw_content=item.raw_content,
                format=item.format,
                fields=item.fields,
                role=request.role,
                target_destination=request.target_destination,
            )
            v_resp = await cls.validate_pipeline(v_req)
            results.append(v_resp)

            if v_resp.status == PipelineState.READY and v_resp.decision == "ALLOW":
                passed += 1
            elif v_resp.status == PipelineState.BLOCKED:
                blocked += 1
            elif v_resp.status == PipelineState.FAILED:
                failed += 1

            if v_resp.detection_status == "REVIEW" or v_resp.policy_status == "REVIEW":
                review_required += 1

        total = len(request.datasets)
        # Fail-closed summary check
        fail_closed_triggered = (blocked > 0 or failed > 0)
        overall_decision = "ALLOW" if (passed == total and not fail_closed_triggered) else "BLOCK"

        summary = BatchSummary(
            batch_id=request.batch_id,
            total_datasets=total,
            passed=passed,
            blocked=blocked,
            failed=failed,
            review_required=review_required,
            overall_decision=overall_decision,
            fail_closed_triggered=fail_closed_triggered,
        )

        return PipelineBatchResponse(
            batch_id=request.batch_id,
            summary=summary,
            results=results,
        )

    @classmethod
    async def get_report(cls, pipeline_id: str) -> Optional[PipelineReportResponse]:
        """Generate machine-readable summary and human-readable Markdown report."""
        record = await PipelineRepository.get_by_pipeline_id(pipeline_id)
        if not record:
            return None

        markdown_rep = record.get("report_markdown")
        if not markdown_rep:
            # Reconstruct from summary
            summary = record.get("summary", {})
            markdown_rep = f"# University DataShield – Pipeline Report\n\nPipeline: `{pipeline_id}`\nStatus: {record['status']}\nDecision: {record['decision']}"

        return PipelineReportResponse(
            pipeline_id=record["pipeline_id"],
            execution_id=record["execution_id"],
            dataset_name=record["dataset_name"],
            status=record["status"],
            decision=record["decision"],
            summary=record.get("summary", {}),
            markdown_report=markdown_rep,
        )

    @staticmethod
    def _generate_markdown_report(resp: PipelineValidateResponse) -> str:
        """Generate clean, privacy-safe Markdown report."""
        violations_md = ""
        if resp.policy_violations:
            violations_md = "\n".join(
                f"- **Field `{v.field}`** ({v.classification}): Requires `{v.required_action}`, actual is `{v.actual_action}`. *Reason: {v.reason}*"
                for v in resp.policy_violations
            )
        else:
            violations_md = "None. All sensitive fields meet required masking policies."

        recom_md = ""
        if resp.recommended_actions:
            recom_md = "\n".join(
                f"- **`{r.field}`** → Apply `{r.recommended_action}` (Preview: `{r.preview}`)"
                for r in resp.recommended_actions
            )
        else:
            recom_md = "No pending transformations required."

        return f"""# University DataShield — Pipeline Validation Report

### Execution Summary
- **Pipeline ID**: `{resp.pipeline_id}`
- **Execution ID**: `{resp.execution_id}`
- **Dataset**: `{resp.dataset_name}`
- **Status**: `{resp.status.value}`
- **Decision**: **{resp.decision}**
- **Risk Level**: `{resp.risk_level}` (Score: {resp.risk_score}/100)
- **Requesting Role**: `{resp.role}`
- **Target Destination**: `{resp.target_destination}`
- **Policy Version**: `{resp.policy_version}`
- **Audit Reference**: `{resp.audit_reference or 'N/A'}`

---

### Security Gate Assessment
- **Sensitive-Field Detection**: `{resp.detection_status}`
- **Policy Compliance**: `{resp.policy_status}`
- **Authorization Check**: `{resp.authorization_status}`
- **Publication Gate**: **{resp.decision}**

---

### Sensitive Fields Detected
{', '.join(f'`{f}`' for f in resp.sensitive_fields) if resp.sensitive_fields else 'No sensitive fields detected.'}

### Policy Violations
{violations_md}

### Recommended Actions
{recom_md}

---
*Notice: Evaluated under University DataShield Phase 10 fail-closed analytical security controls. Zero raw PII persisted.*
"""
