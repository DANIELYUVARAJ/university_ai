# tests/test_phase10_pipeline.py
"""
University DataShield – Phase 10 Test Suite
Analytical Pipeline Integration, Safe Ingestion, Fail-Closed Security Gate,
Batch Processing, Idempotency, Audit Trail, and Data Minimization Verification.
"""

import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from pipeline.ingestion import DatasetIngestionService
from pipeline.schemas import (
    PipelineState,
    DatasetFormat,
    PipelineValidateRequest,
    PipelinePublishRequest,
    PipelineBatchRequest,
    BatchValidationItem,
)
from pipeline.pipeline_service import PipelineService
from policies.schemas import FieldValidationInput, ProtectionAction
from audit.audit_service import AuditService
from database import get_db

client = TestClient(app)

SAMPLE_VALID_CSV = """student_id,full_name,student_email,contact_phone,cgpa,department
STU_DEMO_001,John Doe,student001@example.edu,+91-9000000001,3.85,Computer Science
STU_DEMO_002,Jane Smith,student002@example.edu,+91-9000000002,3.90,Data Science
"""

SAMPLE_VALID_JSON = json.dumps([
    {
        "student_id": "STU_DEMO_001",
        "full_name": "John Doe",
        "student_email": "student001@example.edu",
        "contact_phone": "+91-9000000001",
        "cgpa": 3.85,
        "department": "Computer Science"
    },
    {
        "student_id": "STU_DEMO_002",
        "full_name": "Jane Smith",
        "student_email": "student002@example.edu",
        "contact_phone": "+91-9000000002",
        "cgpa": 3.90,
        "department": "Data Science"
    }
])


# ==============================================================================
# A. INGESTION TESTS
# ==============================================================================

def test_ingestion_valid_csv():
    schema, inputs = DatasetIngestionService.ingest("students.csv", SAMPLE_VALID_CSV)
    assert schema.dataset_name == "students.csv"
    assert schema.format == DatasetFormat.CSV
    assert schema.row_count == 2
    field_names = [f.field_name for f in schema.fields]
    assert "student_id" in field_names
    assert "student_email" in field_names
    assert "cgpa" in field_names
    assert len(inputs) == 6


def test_ingestion_valid_json():
    schema, inputs = DatasetIngestionService.ingest("students.json", SAMPLE_VALID_JSON)
    assert schema.dataset_name == "students.json"
    assert schema.format == DatasetFormat.JSON
    assert schema.row_count == 2
    field_names = [f.field_name for f in schema.fields]
    assert "student_id" in field_names
    assert "contact_phone" in field_names
    assert len(inputs) == 6


def test_ingestion_invalid_csv():
    with pytest.raises(ValueError, match="Invalid CSV format|Empty dataset"):
        DatasetIngestionService.ingest("broken.csv", "   \n\n  ")


def test_ingestion_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON format"):
        DatasetIngestionService.ingest("broken.json", '{"student_id": "STU_001", "name": ')


def test_ingestion_empty_input():
    with pytest.raises(ValueError, match="Empty dataset"):
        DatasetIngestionService.ingest("empty.csv", "")


def test_ingestion_data_minimization():
    """Verify that raw rows are NOT kept inside the ExtractedSchema object."""
    schema, inputs = DatasetIngestionService.ingest("students.csv", SAMPLE_VALID_CSV)
    schema_dict = schema.model_dump()
    assert "records" not in schema_dict
    assert "data" not in schema_dict
    assert "rows" not in schema_dict


# ==============================================================================
# B. PIPELINE VALIDATION & FAIL-CLOSED GATES
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_validation_unprotected_blocks():
    """An analytical dataset with raw sensitive fields must be BLOCKED."""
    req = PipelineValidateRequest(
        dataset_name="unprotected_students.csv",
        raw_content=SAMPLE_VALID_CSV,
        format=DatasetFormat.CSV,
        role="DATA_ENGINEER",
    )
    resp = await PipelineService.validate_pipeline(req)
    assert resp.status == PipelineState.BLOCKED
    assert resp.decision == "BLOCK"
    assert resp.policy_status == "FAIL"
    assert len(resp.policy_violations) > 0
    assert len(resp.sensitive_fields) >= 3
    assert len(resp.recommended_actions) > 0
    assert resp.audit_reference is not None


@pytest.mark.asyncio
async def test_pipeline_validation_properly_protected_ready():
    """When all sensitive fields are properly protected according to policy, status is READY."""
    fields = [
        FieldValidationInput(name="student_id", classification="STUDENT_ID", actual_action=ProtectionAction.HASH, sample_value="STU_DEMO_001"),
        FieldValidationInput(name="full_name", classification="NAME", actual_action=ProtectionAction.MASK, sample_value="John Doe"),
        FieldValidationInput(name="student_email", classification="EMAIL", actual_action=ProtectionAction.MASK, sample_value="student001@example.edu"),
        FieldValidationInput(name="contact_phone", classification="PHONE", actual_action=ProtectionAction.MASK, sample_value="+91-9000000001"),
        FieldValidationInput(name="cgpa", classification="ACADEMIC_DATA", actual_action=ProtectionAction.NONE, sample_value="3.85"),
        FieldValidationInput(name="department", classification="ACADEMIC_DATA", actual_action=ProtectionAction.NONE, sample_value="Computer Science"),
    ]
    req = PipelineValidateRequest(
        dataset_name="protected_students.csv",
        fields=fields,
        role="SECURITY_ADMIN",
    )
    resp = await PipelineService.validate_pipeline(req)
    assert resp.status == PipelineState.READY
    assert resp.decision == "ALLOW"
    assert resp.policy_status == "PASS"
    assert len(resp.policy_violations) == 0


@pytest.mark.asyncio
async def test_pipeline_validation_unauthorized_role():
    """Even if fields are protected, an unauthorized role (e.g. FACULTY) is BLOCKED."""
    fields = [
        FieldValidationInput(name="student_id", classification="STUDENT_ID", actual_action=ProtectionAction.HASH, sample_value="STU_DEMO_001"),
        FieldValidationInput(name="full_name", classification="NAME", actual_action=ProtectionAction.MASK, sample_value="John Doe"),
    ]
    req = PipelineValidateRequest(
        dataset_name="faculty_attempt.csv",
        fields=fields,
        role="FACULTY",  # FACULTY cannot publish
    )
    resp = await PipelineService.validate_pipeline(req)
    assert resp.status == PipelineState.BLOCKED
    assert resp.decision == "BLOCK"
    assert resp.authorization_status == "FAIL"


@pytest.mark.asyncio
async def test_pipeline_client_side_bypass_rejected():
    """Client asserting client_approved=True must be ignored by backend verification."""
    req = PipelineValidateRequest(
        dataset_name="bypass_attempt.csv",
        raw_content=SAMPLE_VALID_CSV,
        role="DATA_ENGINEER",
        client_approved=True,  # Adversarial client attempting to bypass gate
    )
    resp = await PipelineService.validate_pipeline(req)
    assert resp.status == PipelineState.BLOCKED
    assert resp.decision == "BLOCK"


@pytest.mark.asyncio
async def test_pipeline_publish_blocked_on_unprotected():
    """Publishing a blocked pipeline must fail closed and return success=False."""
    val_req = PipelineValidateRequest(
        dataset_name="publish_blocked.csv",
        raw_content=SAMPLE_VALID_CSV,
        role="SECURITY_ADMIN",
    )
    val_resp = await PipelineService.validate_pipeline(val_req)

    pub_req = PipelinePublishRequest(
        pipeline_id=val_resp.pipeline_id,
        role="SECURITY_ADMIN",
        raw_content=SAMPLE_VALID_CSV,
        client_approved=True,
    )
    pub_resp = await PipelineService.publish_pipeline(pub_req)
    assert pub_resp.success is False
    assert pub_resp.decision == "BLOCK"
    assert pub_resp.status == PipelineState.BLOCKED


@pytest.mark.asyncio
async def test_pipeline_publish_allowed_on_compliant():
    """Publishing a fully compliant dataset succeeds and updates state to PUBLISHED."""
    fields = [
        FieldValidationInput(name="student_id", classification="STUDENT_ID", actual_action=ProtectionAction.HASH, sample_value="STU_DEMO_001"),
        FieldValidationInput(name="student_email", classification="EMAIL", actual_action=ProtectionAction.MASK, sample_value="student001@example.edu"),
    ]
    val_req = PipelineValidateRequest(
        dataset_name="publish_ready.csv",
        fields=fields,
        role="SECURITY_ADMIN",
    )
    val_resp = await PipelineService.validate_pipeline(val_req)
    assert val_resp.status == PipelineState.READY

    pub_req = PipelinePublishRequest(
        pipeline_id=val_resp.pipeline_id,
        role="SECURITY_ADMIN",
        fields=fields,
    )
    pub_resp = await PipelineService.publish_pipeline(pub_req)
    assert pub_resp.success is True
    assert pub_resp.decision == "ALLOW"
    assert pub_resp.status == PipelineState.PUBLISHED
    assert pub_resp.published_at is not None


# ==============================================================================
# C. IDEMPOTENCY & SAFE RETRY SEMANTICS
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_idempotency():
    """Repeated calls with same execution_id return identical cached response."""
    exec_id = "EX-2026-TESTIDEMP01"
    req = PipelineValidateRequest(
        dataset_name="idempotent_test.csv",
        raw_content=SAMPLE_VALID_CSV,
        execution_id=exec_id,
        role="DATA_ENGINEER",
    )
    resp1 = await PipelineService.validate_pipeline(req)
    resp2 = await PipelineService.validate_pipeline(req)

    assert resp1.pipeline_id == resp2.pipeline_id
    assert resp1.execution_id == resp2.execution_id
    assert resp1.status == resp2.status
    assert resp1.decision == resp2.decision
    assert resp1.audit_reference == resp2.audit_reference


@pytest.mark.asyncio
async def test_pipeline_safe_retry_semantics():
    """Retrying without fixing masking remains BLOCKED; retrying with proper masking transitions to READY."""
    pl_id = "PL-2026-RETRYDEMO"
    
    # Attempt 1: Unprotected -> BLOCKED
    req1 = PipelineValidateRequest(
        pipeline_id=pl_id,
        dataset_name="retry_dataset.csv",
        raw_content=SAMPLE_VALID_CSV,
        role="DATA_ENGINEER",
    )
    resp1 = await PipelineService.validate_pipeline(req1)
    assert resp1.status == PipelineState.BLOCKED

    # Attempt 2 (Retry unchanged) -> STILL BLOCKED
    req2 = PipelineValidateRequest(
        pipeline_id=pl_id,
        dataset_name="retry_dataset.csv",
        raw_content=SAMPLE_VALID_CSV,
        role="DATA_ENGINEER",
    )
    resp2 = await PipelineService.validate_pipeline(req2)
    assert resp2.status == PipelineState.BLOCKED

    # Attempt 3 (Retry with proper masking applied) -> READY
    proper_fields = [
        FieldValidationInput(name="student_id", classification="STUDENT_ID", actual_action=ProtectionAction.HASH, sample_value="STU_001"),
        FieldValidationInput(name="full_name", classification="NAME", actual_action=ProtectionAction.MASK, sample_value="John Doe"),
        FieldValidationInput(name="student_email", classification="EMAIL", actual_action=ProtectionAction.MASK, sample_value="student@example.edu"),
        FieldValidationInput(name="contact_phone", classification="PHONE", actual_action=ProtectionAction.MASK, sample_value="+91-9000000001"),
        FieldValidationInput(name="cgpa", classification="ACADEMIC_DATA", actual_action=ProtectionAction.NONE, sample_value="3.85"),
        FieldValidationInput(name="department", classification="ACADEMIC_DATA", actual_action=ProtectionAction.NONE, sample_value="CS"),
    ]
    req3 = PipelineValidateRequest(
        pipeline_id=pl_id,
        dataset_name="retry_dataset.csv",
        fields=proper_fields,
        role="SECURITY_ADMIN",
    )
    resp3 = await PipelineService.validate_pipeline(req3)
    assert resp3.status == PipelineState.READY
    assert resp3.decision == "ALLOW"


# ==============================================================================
# D. BATCH VALIDATION (FAIL-CLOSED)
# ==============================================================================

@pytest.mark.asyncio
async def test_batch_validation_partial_failure_fail_closed():
    """If one dataset in a batch has policy violations, the overall batch decision must be BLOCK."""
    safe_fields = [
        FieldValidationInput(name="student_id", classification="STUDENT_ID", actual_action=ProtectionAction.HASH, sample_value="STU_01"),
    ]
    batch_req = PipelineBatchRequest(
        batch_id="batch_analytics_2026_01",
        role="SECURITY_ADMIN",
        datasets=[
            BatchValidationItem(dataset_name="clean_students.json", fields=safe_fields),
            BatchValidationItem(dataset_name="unprotected_attendance.csv", raw_content=SAMPLE_VALID_CSV),
        ]
    )
    batch_resp = await PipelineService.batch_validate(batch_req)
    assert batch_resp.summary.total_datasets == 2
    assert batch_resp.summary.passed == 1
    assert batch_resp.summary.blocked == 1
    assert batch_resp.summary.fail_closed_triggered is True
    assert batch_resp.summary.overall_decision == "BLOCK"


@pytest.mark.asyncio
async def test_batch_validation_all_clean_allows():
    """If all datasets in a batch pass, the batch decision is ALLOW."""
    safe_fields = [
        FieldValidationInput(name="student_id", classification="STUDENT_ID", actual_action=ProtectionAction.HASH, sample_value="STU_01"),
    ]
    batch_req = PipelineBatchRequest(
        batch_id="batch_analytics_clean",
        role="SECURITY_ADMIN",
        datasets=[
            BatchValidationItem(dataset_name="clean1.json", fields=safe_fields),
            BatchValidationItem(dataset_name="clean2.json", fields=safe_fields),
        ]
    )
    batch_resp = await PipelineService.batch_validate(batch_req)
    assert batch_resp.summary.total_datasets == 2
    assert batch_resp.summary.passed == 2
    assert batch_resp.summary.blocked == 0
    assert batch_resp.summary.overall_decision == "ALLOW"


# ==============================================================================
# E. AUDIT INTEGRITY & PRIVACY (DATA MINIMIZATION)
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_audit_event_logged_and_tamper_evident():
    """Verify pipeline operations append valid audit events and audit chain remains unbroken."""
    val_req = PipelineValidateRequest(
        dataset_name="audit_test.csv",
        raw_content=SAMPLE_VALID_CSV,
        role="DATA_ENGINEER",
    )
    resp = await PipelineService.validate_pipeline(val_req)
    assert resp.audit_reference is not None

    integrity = await AuditService.check_integrity()
    assert integrity.status == "VALID"
    assert integrity.events_checked > 0


@pytest.mark.asyncio
async def test_zero_raw_pii_stored_in_pipeline_runs_db():
    """Verify that SQLite pipeline_runs table contains NO raw sample values."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT summary_json, report_markdown FROM pipeline_runs")
        rows = await cursor.fetchall()
        for row in rows:
            summary_str = row[0] or ""
            report_str = row[1] or ""
            # Ensure raw emails or phone numbers from CSV were not persisted
            assert "student001@example.edu" not in summary_str
            assert "+91-9000000001" not in summary_str
            assert "+91-9000000001" not in report_str
    finally:
        await db.close()


# ==============================================================================
# F. FASTAPI HTTP ENDPOINT TESTS
# ==============================================================================

def test_api_pipeline_validate():
    payload = {
        "dataset_name": "api_test.csv",
        "raw_content": SAMPLE_VALID_CSV,
        "role": "DATA_ENGINEER",
    }
    res = client.post("/pipeline/validate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "BLOCKED"
    assert data["decision"] == "BLOCK"
    assert len(data["policy_violations"]) > 0


def test_api_pipeline_preview():
    payload = {
        "dataset_name": "preview_test.csv",
        "raw_content": SAMPLE_VALID_CSV,
        "role": "DATA_ENGINEER",
    }
    res = client.post("/pipeline/preview", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "masking_previews" in data
    assert len(data["masking_previews"]) > 0


def test_api_pipeline_runs_list():
    res = client.get("/pipeline/runs")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_api_pipeline_report():
    # First validate to get a pipeline id
    val_res = client.post("/pipeline/validate", json={
        "dataset_name": "report_test.csv",
        "raw_content": SAMPLE_VALID_CSV,
        "role": "DATA_ENGINEER",
    })
    pl_id = val_res.json()["pipeline_id"]

    res = client.get(f"/pipeline/{pl_id}/report")
    assert res.status_code == 200
    rep_data = res.json()
    assert rep_data["pipeline_id"] == pl_id
    assert "University DataShield — Pipeline Validation Report" in rep_data["markdown_report"]
