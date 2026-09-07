"""
University DataShield – Backend
Phase 1 & 2: Foundation + Sensitive Field Discovery Engine

FastAPI application entry point.

Endpoints
----------
Phase 1:
  GET /health   – liveness + DB check

Phase 2:
  POST /scan          – scan a dataset schema for sensitive fields
  GET  /scan/schema   – return the built-in synthetic demo schema
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, verify_db, get_db
from detection import scan_fields, ScanRequest, ScanResponse
from synthetic_schema import SYNTHETIC_SCHEMA
from evaluation import EvaluationService
from policies import (
    PolicyEngine,
    PolicyValidationRequest,
    PolicyValidationResponse,
    MaskingPreviewRequest,
    MaskingPreviewResponse,
    apply_masking,
)
from access import AccessEngine, Role
from publication import (
    PublicationGate,
    PublicationCheckRequest,
    PublicationCheckResponse,
    PublishExecutionRequest,
    PublishExecutionResponse,
)
from audit import (
    AuditService,
    AuditAction,
    AuditFilterParams,
    AuditIntegrityResponse,
    AuditEventRecord,
)
from governance import (
    GovernanceService,
    GovernanceRepository,
    ProposeChangeRequest,
    ApproveChangeRequest,
    RejectChangeRequest,
    RollbackRequest,
    RollbackResponse,
    PolicyChangeRecord,
    PolicyVersionRecord,
    PolicyDiffResponse,
)
from security_validation import (
    SecurityValidationRunner,
    SecurityValidationReport,
    SecurityMetrics,
)
from demo import (
    DemoService,
    DashboardSummaryResponse,
    DemoResetResponse,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("datashield")

# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise resources on startup; clean up on shutdown."""
    logger.info("University DataShield backend starting …")
    await init_db()
    # Seed initial baseline policy version v1.0 if not present
    await GovernanceRepository.ensure_initial_version()
    logger.info("Database and governance baselines ready.")
    yield
    logger.info("University DataShield backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="University DataShield API",
    description=(
        "Automated Sensitive-Field Discovery & Masking Validator. "
        "Phase 2 – Detection Engine."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# CORS – allow the Vite dev server (port 5173) and any localhost origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes – Phase 1
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Health check",
    tags=["infrastructure"],
    response_description="Service liveness and dependency status",
)
async def health() -> dict:
    """
    Return the liveness status of the API and its dependencies.
    The ``database`` field reflects an actual SQLite query.
    """
    db_status = await verify_db()
    return {
        "status": "ok",
        "service": "university-datashield",
        "version": "0.8.0",
        "phase": 8,
        "database": db_status,
        "data_mode": "synthetic",
    }


# ---------------------------------------------------------------------------
# Routes – Phase 2
# ---------------------------------------------------------------------------

@app.get(
    "/scan/schema",
    summary="Return the built-in synthetic demo schema",
    tags=["detection"],
    response_description="Synthetic dataset schema ready for POST /scan",
)
async def get_synthetic_schema() -> dict:
    """
    Returns the pre-built synthetic university dataset schema.
    All sample values are synthetic — no real personal data.
    """
    return SYNTHETIC_SCHEMA


@app.post(
    "/scan",
    summary="Scan a dataset schema for sensitive fields",
    tags=["detection"],
    response_model=ScanResponse,
    response_description="Per-field detection results with classification and confidence",
)
async def scan_dataset(request: ScanRequest) -> ScanResponse:
    """
    Run the Sensitive Field Discovery Engine on the provided schema.

    The engine applies four signals per field:
    1. Field-name matching (rule-based)
    2. Value-pattern detection (regex on sample_pattern)
    3. Data-type analysis
    4. Semantic classification

    No real personal data is required or stored.
    Only field metadata, classification, and confidence are persisted.
    """
    logger.info("Scanning dataset '%s' (%d fields)", request.dataset_name, len(request.fields))

    # Run detection engine
    results = scan_fields(request.fields)

    sensitive_count = sum(
        1 for r in results if r.classification != "NON_SENSITIVE"
    )

    # Persist scan summary + per-field results to SQLite
    try:
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                INSERT INTO scan_results (dataset_name, fields_scanned, sensitive_count)
                VALUES (?, ?, ?)
                """,
                (request.dataset_name, len(request.fields), sensitive_count),
            )
            scan_id: int = cursor.lastrowid  # type: ignore[assignment]

            for r in results:
                await db.execute(
                    """
                    INSERT INTO field_results
                        (scan_id, field_name, data_type, classification, confidence, reasons)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_id,
                        r.field,
                        r.data_type,
                        r.classification,
                        r.confidence,
                        json.dumps(r.reasons),
                    ),
                )
            await db.commit()
            logger.info("Scan persisted — scan_id=%d", scan_id)
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Failed to persist scan results: %s", exc)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    # Phase 6: Record SCAN action to immutable audit trail
    try:
        await AuditService.log_event(
            action=AuditAction.SCAN,
            actor_role="DATA_ENGINEER",
            actor_id="engineer-demo",
            result=f"{len(results)}_FIELDS_SCANNED",
            dataset=request.dataset_name,
            reason=f"Discovered {sensitive_count} sensitive fields out of {len(results)} total scanned",
            metadata={"fields_scanned": len(results), "sensitive_count": sensitive_count},
        )
    except Exception as audit_exc:
        logger.warning("Failed to record scan audit event: %s", audit_exc)

    return ScanResponse(
        dataset_name=request.dataset_name,
        scan_id=scan_id,
        fields_scanned=len(results),
        sensitive_count=sensitive_count,
        results=results,
    )


# ---------------------------------------------------------------------------
# Routes – Phase 3 (Evaluation & Baseline Comparison)
# ---------------------------------------------------------------------------

@app.post(
    "/evaluate",
    summary="Evaluate Baseline vs DataShield against ground truth",
    tags=["evaluation"],
    response_description="Metrics comparison and error analysis",
)
@app.get(
    "/evaluate",
    summary="Evaluate Baseline vs DataShield against ground truth",
    tags=["evaluation"],
    response_description="Metrics comparison and error analysis",
)
async def evaluate_models(custom_dataset: list[dict] | None = None) -> dict:
    """
    Run the keyword baseline detector and the multi-signal DataShield detector
    against the synthetic validation dataset with ground truth labels.

    Computes:
    - Precision, Recall, F1, Accuracy
    - True Positives, True Negatives, False Positives, False Negatives
    - Error analysis table identifying exact mistakes per model
    """
    eval_service = EvaluationService()
    results = eval_service.run_evaluation(custom_dataset)

    # Persist summary to SQLite
    try:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO evaluation_runs (
                    total_fields, baseline_f1, datashield_f1, baseline_accuracy, datashield_accuracy
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    results["total_fields"],
                    results["baseline"]["f1"],
                    results["datashield"]["f1"],
                    results["baseline"]["accuracy"],
                    results["datashield"]["accuracy"],
                ),
            )
            await db.commit()
        finally:
            await db.close()
    except Exception as exc:
        logger.warning("Could not persist evaluation run: %s", exc)

    return results


# ---------------------------------------------------------------------------
# Routes – Phase 4 (Masking Policy Engine)
# ---------------------------------------------------------------------------

@app.get(
    "/policies",
    summary="Get active masking policies and rules",
    tags=["policies"],
    response_description="Active policy version, classification defaults, and field overrides",
)
async def get_policies() -> dict:
    """Return configured classification policies, field overrides, and active version metadata."""
    engine = await PolicyEngine.load_active()
    return engine.get_active_policies()


@app.post(
    "/policies/validate",
    summary="Validate field protection actions against masking policies",
    tags=["policies"],
    response_model=PolicyValidationResponse,
    response_description="Validation status (PASS/FAIL/REVIEW) and compliance summary",
)
async def validate_policies(request: PolicyValidationRequest) -> PolicyValidationResponse:
    """
    Validate field protection against policies.
    Compares: Detected Classification -> Required Policy -> Actual Protection.
    Returns PASS, FAIL, or REVIEW with human-readable rationale.
    Privacy guarantee: Never persists raw sensitive values.
    """
    engine = await PolicyEngine.load_active()
    response = engine.validate_dataset(request)

    # Persist summary (no raw sensitive data is ever stored)
    try:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO policy_validations (
                    policy_version, dataset_name, overall_status, total_evaluated, violations, compliance
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    response.policy_version,
                    request.dataset_name,
                    response.overall_status.value,
                    response.summary.total_evaluated,
                    response.summary.violations,
                    response.summary.overall_compliance,
                ),
            )
            await db.commit()
        finally:
            await db.close()
    except Exception as exc:
        logger.warning("Could not persist policy validation summary: %s", exc)

    # Phase 6: Record POLICY_VALIDATION event to audit trail
    try:
        await AuditService.log_event(
            action=AuditAction.POLICY_VALIDATION,
            actor_role="ANALYST",
            actor_id="analyst-demo",
            result=response.overall_status.value,
            dataset=request.dataset_name,
            reason=f"{response.summary.violations} violation(s) found across {response.summary.total_evaluated} evaluated fields; compliance {response.summary.overall_compliance}%",
            policy_version=response.policy_version,
            metadata={
                "total_evaluated": response.summary.total_evaluated,
                "violations": response.summary.violations,
                "compliance": response.summary.overall_compliance,
            },
        )
    except Exception as audit_exc:
        logger.warning("Failed to record policy validation audit event: %s", audit_exc)

    return response


@app.post(
    "/policies/preview",
    summary="Demonstrate masking transformation on synthetic sample",
    tags=["policies"],
    response_model=MaskingPreviewResponse,
    response_description="Masked demonstration output for synthetic value",
)
async def preview_masking(request: MaskingPreviewRequest) -> MaskingPreviewResponse:
    """
    Demonstrate synthetic masking on sample value for interactive validation preview.
    Privacy guarantee: Only operates on synthetic demonstration data. Never persisted.
    """
    masked = apply_masking(
        val=request.value,
        action=request.action,
        field_name=request.field_name,
        data_type=request.data_type or "string",
    )
    return MaskingPreviewResponse(
        field_name=request.field_name,
        action=request.action,
        original_present=bool(request.value),
        masked_value=masked,
        is_synthetic=True,
    )


# ---------------------------------------------------------------------------
# Routes – Phase 5 (Role-Based Access + Publication Gate)
# ---------------------------------------------------------------------------

@app.get(
    "/roles",
    summary="Get all demo roles and their permission capabilities",
    tags=["access"],
    response_description="List of roles with description and permission matrix",
)
async def get_roles() -> list[dict]:
    """Retrieve the full role-policy permission matrix."""
    return AccessEngine.get_all_roles()


@app.get(
    "/roles/{role_name}",
    summary="Get details and permissions for a specific role",
    tags=["access"],
    response_description="Role details and allowed actions",
)
async def get_role(role_name: str) -> dict:
    """Retrieve details for a specific role."""
    try:
        return AccessEngine.get_role_details(role_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/publish-check",
    summary="Pre-publication safety check against role authorization and masking policies",
    tags=["publication"],
    response_model=PublicationCheckResponse,
    response_description="Gate decision (ALLOW/BLOCK) with detailed policy breakdown",
)
async def check_publication(request: PublicationCheckRequest) -> PublicationCheckResponse:
    """
    Evaluates role permissions and mandatory masking policies using the active policy version.
    Follows strict DEFAULT DENY.
    Never allows unmasked sensitive data to be published.
    Authoritatively records PUBLICATION_CHECK in the immutable audit trail.
    """
    engine = await PolicyEngine.load_active()
    gate = PublicationGate(policy_engine=engine)
    response = gate.evaluate(request)

    # Format human-explainable reason summary without raw PII
    if response.reasons:
        reasons_summary = "; ".join(
            r if isinstance(r, str) else f"{r.get('field', 'field')}: {r.get('reason', '')}"
            for r in response.reasons[:3]
        )
    else:
        reasons_summary = "All fields satisfied required masking policies and role authorized"

    # Authoritative backend audit record
    try:
        await AuditService.log_event(
            action=AuditAction.PUBLICATION_CHECK,
            actor_role=response.role,
            actor_id=f"{response.role.lower()}-demo",
            result=response.decision.value,
            dataset=response.dataset_name,
            reason=reasons_summary,
            policy_version=response.policy_version,
            metadata={
                "status": response.status.value,
                "authorized": response.authorized,
                "policy_compliant": response.policy_compliant,
                "reasons_count": len(response.reasons),
            },
        )
    except Exception as audit_exc:
        logger.warning("Failed to record publication check audit event: %s", audit_exc)

    return response


@app.post(
    "/publish",
    summary="Simulate dataset publication to analytical destination",
    tags=["publication"],
    response_model=PublishExecutionResponse,
    response_description="Publication outcome. Independently re-validated by backend gate.",
)
async def publish_dataset(request: PublishExecutionRequest) -> PublishExecutionResponse:
    """
    Backend-enforced publication execution.
    CRITICAL: Does NOT trust any client-side approval flag.
    Independently re-evaluates role authorization and mandatory masking policies.
    Logs publication attempt and authoritative audit event.
    """
    engine = await PolicyEngine.load_active()
    gate = PublicationGate(policy_engine=engine)
    response = gate.execute_publish(request)

    # Persist publication attempt to SQLite (No raw PII stored!)
    try:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO publication_attempts (
                    dataset_name, role, decision, status, reasons_json, policy_version
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request.dataset_name,
                    request.role.upper().strip(),
                    response.decision.value,
                    response.status.value,
                    json.dumps(response.reasons),
                    engine.version,
                ),
            )
            await db.commit()
        finally:
            await db.close()
    except Exception as exc:
        logger.warning("Could not persist publication attempt: %s", exc)

    # Authoritative backend audit record
    try:
        if response.status.value == "UNAUTHORIZED":
            audit_action = AuditAction.ACCESS_DENIAL
            audit_reason = f"Unauthorized publication attempt by role {response.role}"
        elif response.decision.value == "ALLOW":
            audit_action = AuditAction.PUBLICATION
            audit_reason = f"Published safely to destination {request.target_destination}"
        else:
            audit_action = AuditAction.PUBLICATION
            audit_reason = f"Publication blocked by security gate: {response.status.value}"

        await AuditService.log_event(
            action=audit_action,
            actor_role=response.role,
            actor_id=f"{response.role.lower()}-demo",
            result=response.decision.value,
            dataset=response.dataset_name,
            reason=audit_reason,
            policy_version=engine.version,
            metadata={
                "target_destination": request.target_destination,
                "status": response.status.value,
                "success": response.success,
            },
        )
    except Exception as audit_exc:
        logger.warning("Failed to record publication audit event: %s", audit_exc)

    return response


# ---------------------------------------------------------------------------
# Routes – Phase 6 (Complete Audit Trail + Policy Change Governance + Rollback)
# ---------------------------------------------------------------------------

@app.get(
    "/audit",
    summary="Query immutable audit trail records with filters",
    tags=["governance"],
    response_model=list[AuditEventRecord],
    response_description="Chronological audit records filtered by query parameters",
)
async def get_audit_trail(
    action: str | None = None,
    actor_role: str | None = None,
    result: str | None = None,
    policy_version: str | None = None,
    dataset: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEventRecord]:
    """
    Retrieve append-only, explainable audit trail events.
    Guaranteed: Contains metadata only; no raw personal data is ever recorded.
    """
    audit_action = None
    if action:
        try:
            audit_action = AuditAction(action.upper().strip())
        except ValueError:
            pass

    filters = AuditFilterParams(
        action=audit_action,
        actor_role=actor_role.upper().strip() if actor_role else None,
        result=result.upper().strip() if result else None,
        policy_version=policy_version.strip() if policy_version else None,
        dataset=dataset.strip() if dataset else None,
        limit=min(limit, 500),
        offset=offset,
    )
    return await AuditService.get_events(filters)


@app.get(
    "/audit/integrity",
    summary="Verify cryptographic SHA-256 hash chaining integrity of the audit trail",
    tags=["governance"],
    response_model=AuditIntegrityResponse,
    response_description="Verification status (VALID / COMPROMISED) across all recorded events",
)
async def verify_audit_integrity() -> AuditIntegrityResponse:
    """
    Cryptographically inspect the audit log hash chain.
    Proves that no audit record has been tampered with or modified.
    """
    return await AuditService.check_integrity()


@app.get(
    "/policy-changes",
    summary="List all policy change requests",
    tags=["governance"],
    response_model=list[PolicyChangeRecord],
    response_description="Historical and pending policy change proposals",
)
async def list_policy_changes() -> list[PolicyChangeRecord]:
    """Retrieve all policy change requests (PENDING, APPROVED, REJECTED)."""
    return await GovernanceService.get_all_change_requests()


@app.post(
    "/policies/propose",
    summary="Propose a policy change (holds change in PENDING state)",
    tags=["governance"],
    response_model=PolicyChangeRecord,
    response_description="Newly created change request awaiting Security Admin approval",
)
async def propose_policy_change(request: ProposeChangeRequest) -> PolicyChangeRecord:
    """
    Propose an update to masking policies.
    Crucial guarantee: Does NOT alter active policy behavior; holds in PENDING status.
    Requires independent Security Admin approval before becoming active.
    """
    return await GovernanceService.propose_change(request)


@app.post(
    "/policies/approve",
    summary="Approve a pending policy change (SECURITY_ADMIN only; No self-approval)",
    tags=["governance"],
    response_model=PolicyVersionRecord,
    response_description="New immutable policy version created and activated",
)
async def approve_policy_change(request: ApproveChangeRequest) -> PolicyVersionRecord:
    """
    Approve a pending change request.
    Strict enforcement:
      - Only SECURITY_ADMIN can approve (403 GOVERNANCE_ROLE_REQUIRED).
      - NO SELF-APPROVAL: Proposer cannot approve their own change (409 SELF_APPROVAL_BLOCKED).
      - Creates a new immutable version snapshot (e.g. v1.0 -> v1.1).
    """
    return await GovernanceService.approve_change(request)


@app.post(
    "/policies/reject",
    summary="Reject a pending policy change (SECURITY_ADMIN only)",
    tags=["governance"],
    response_model=PolicyChangeRecord,
    response_description="Updated change request marked as REJECTED",
)
async def reject_policy_change(request: RejectChangeRequest) -> PolicyChangeRecord:
    """Reject a pending change request. Restricted to SECURITY_ADMIN."""
    return await GovernanceService.reject_change(request)


@app.get(
    "/policies/versions",
    summary="List all immutable policy version snapshots",
    tags=["governance"],
    response_model=list[PolicyVersionRecord],
    response_description="Complete version history with status and metadata",
)
async def list_policy_versions() -> list[PolicyVersionRecord]:
    """Retrieve all policy version snapshots in chronological sequence."""
    return await GovernanceService.get_all_versions()


@app.get(
    "/policies/diff",
    summary="Compare configurations between two policy version snapshots",
    tags=["governance"],
    response_model=PolicyDiffResponse,
    response_description="Detailed diff showing changed, added, or unchanged rules",
)
async def diff_policy_versions(
    from_version: str = "v1.0",
    to_version: str = "v1.1",
) -> PolicyDiffResponse:
    """Compare two policy versions to visualize rule transitions and overrides."""
    return await GovernanceService.diff_versions(from_version, to_version)


@app.post(
    "/policies/rollback",
    summary="Roll back to a previous policy version with automatic revalidation",
    tags=["governance"],
    response_model=RollbackResponse,
    response_description="Rollback outcome with post-rollback synthetic validation results",
)
async def rollback_policy(request: RollbackRequest) -> RollbackResponse:
    """
    Safely roll back active policies to a historical target version.
    Security guarantees:
      - Restricted to SECURITY_ADMIN.
      - Preserves complete history (creates e.g. v1.3-rollback).
      - Runs automatic post-rollback validation on synthetic evaluation dataset.
    """
    return await GovernanceService.rollback_policy(request)


# ---------------------------------------------------------------------------
# Routes – Phase 7 (End-to-End Security Validation & Adversarial Testing)
# ---------------------------------------------------------------------------

@app.post(
    "/security-validation/run",
    summary="Execute comprehensive end-to-end security validation suite",
    tags=["security-validation"],
    response_model=SecurityValidationReport,
    response_description="Detailed security report covering 14 realistic adversarial scenarios",
)
async def run_security_validation() -> SecurityValidationReport:
    """
    Execute deterministic security validation scenarios covering:
      - Publication safety & default deny
      - Client-side bypass resistance
      - Unauthorized role denial
      - Cryptographic audit tampering detection
      - Bad policy degradation & rollback recovery
      - Missing policy fail-closed behavior
      - Database privacy & zero raw PII retention
    """
    return await SecurityValidationRunner.run_all()


@app.get(
    "/security-validation/results",
    summary="Get latest security validation results and scenario scorecard",
    tags=["security-validation"],
    response_model=SecurityValidationReport,
    response_description="Scenario scorecard, metrics, and error analysis",
)
async def get_security_validation_results() -> SecurityValidationReport:
    """Retrieve or run the authoritative security validation report."""
    return await SecurityValidationRunner.run_all()


@app.get(
    "/security-validation/metrics",
    summary="Get high-level security effectiveness metrics",
    tags=["security-validation"],
    response_model=SecurityMetrics,
    response_description="Key security performance indicators and rates",
)
async def get_security_validation_metrics() -> SecurityMetrics:
    """Retrieve key metrics: Unsafe Publication Prevention, Unauthorized Block Rate, etc."""
    report = await SecurityValidationRunner.run_all()
    return report.metrics


# ---------------------------------------------------------------------------
# Routes – Phase 8 (Integration, Demo Seeding & Executive Dashboard)
# ---------------------------------------------------------------------------

@app.get(
    "/dashboard/summary",
    summary="Get live executive dashboard summary",
    tags=["dashboard"],
    response_model=DashboardSummaryResponse,
    response_description="Live system health indicators and aggregated governance & security metrics",
)
async def get_dashboard_summary() -> DashboardSummaryResponse:
    """
    Return comprehensive, live metrics sourced from SQLite tables,
    active policies, audit log, and security validation harness.
    """
    return await DemoService.get_dashboard_summary()


@app.post(
    "/demo/reset",
    summary="Reset demo environment to pristine baseline",
    tags=["demo"],
    response_model=DemoResetResponse,
    response_description="Result of deterministic demo environment reset",
)
async def reset_demo_state() -> DemoResetResponse:
    """
    Reset system to pristine demo baseline:
      - Active policy reset to v1.0
      - Pending policy change requests cleared
      - Audit trail verified and marked
    """
    return await DemoService.reset_demo_state()



