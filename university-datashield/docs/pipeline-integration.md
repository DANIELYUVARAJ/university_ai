# University DataShield — Analytical Pipeline Integration Guide

This guide describes how external data pipelines, ETL/ELT processes, and analytics publication workflows integrate with the **University DataShield Automated Security Gate**.

---

## 1. Architectural Workflow

The analytical pipeline follows an uncompromising **Fail-Closed Security Gate**:

```text
SOURCE DATASET (CSV / JSON)
            ↓
    SCHEMA EXTRACTION
            ↓
  DATASHIELD DETECTION (Field name, regex pattern, type inference, contextual signals)
            ↓
   POLICY RESOLUTION (v1.0 active policy rules & overrides)
            ↓
   MASKING VALIDATION (Check actual vs required protection)
            ↓
  RBAC / AUTHORIZATION (Role capability verification)
            ↓
   PUBLICATION GATE (Fail-closed decision engine)
            ↓
      ALLOW / BLOCK
            ↓
   AUDIT RECORDING (SHA-256 tamper-evident cryptographic ledger)
            ↓
  ANALYTICS DESTINATION (Data warehouse / data lake)
```

No client assertion (e.g. `client_approved=true`) is ever trusted. The backend independently evaluates and re-validates the entire dataset before publication.

---

## 2. Authentication & Authorization Concept

External pipeline callers authenticate using secure service tokens mapped to university roles:

| Pipeline Role | Allowed Operations | Publication Permitted? |
| :--- | :--- | :--- |
| `DATA_ENGINEER` | Ingestion, Schema Extraction, Validation | ❌ No (Default Deny) |
| `ANALYST` | Ingestion, Validation, Publication | ✅ Yes (If compliant) |
| `SECURITY_ADMIN` | Ingestion, Validation, Policy Governance, Publication | ✅ Yes (Full privileges) |
| `FACULTY` | Ingestion, Schema Inspection | ❌ No (Default Deny) |
| `PLACEMENT_ADMIN` | Ingestion, Validation | ❌ No (Controlled) |

---

## 3. Integration Step-by-Step

### Step 1: Submit Synthetic Dataset for Validation

Call `POST /pipeline/validate` with your raw synthetic CSV or JSON content.

#### Request Example:
```http
POST /pipeline/validate HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "dataset_name": "fall_2026_student_analytics.csv",
  "raw_content": "student_id,full_name,student_email,contact_phone,cgpa,department\nSTU_2026_001,John Doe,student001@example.edu,+91-9000000001,3.85,Computer Science\nSTU_2026_002,Jane Smith,student002@example.edu,+91-9000000002,3.90,Data Science",
  "format": "CSV",
  "role": "ANALYST",
  "target_destination": "University Analytics Warehouse"
}
```

#### Response Example (Blocked — Policy Violations):
```json
{
  "pipeline_id": "PL-2026-F1A90B",
  "execution_id": "EX-2026-88B12C",
  "dataset_name": "fall_2026_student_analytics.csv",
  "status": "BLOCKED",
  "decision": "BLOCK",
  "detection_status": "PASS",
  "policy_status": "FAIL",
  "authorization_status": "PASS",
  "risk_level": "CRITICAL",
  "risk_score": 75,
  "sensitive_fields": [
    "student_id",
    "full_name",
    "student_email",
    "contact_phone"
  ],
  "policy_violations": [
    {
      "field": "student_id",
      "classification": "DIRECT_IDENTIFIER",
      "required_action": "HASH",
      "actual_action": "NONE",
      "reason": "Direct Identifier requires HASH, but field is unprotected"
    },
    {
      "field": "student_email",
      "classification": "DIRECT_IDENTIFIER",
      "required_action": "MASK",
      "actual_action": "NONE",
      "reason": "Direct Identifier requires MASK, but field is unprotected"
    }
  ],
  "recommended_actions": [
    {
      "field": "student_id",
      "recommended_action": "HASH",
      "reason": "Field classified as DIRECT_IDENTIFIER; requires HASH",
      "preview": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    {
      "field": "student_email",
      "recommended_action": "MASK",
      "reason": "Field classified as DIRECT_IDENTIFIER; requires MASK",
      "preview": "s******@example.edu"
    }
  ],
  "audit_reference": "a9f8721c88d3...",
  "policy_version": "v1.0",
  "role": "ANALYST",
  "target_destination": "University Analytics Warehouse",
  "message": "Pipeline BLOCKED by publication gate. Security violations detected."
}
```

---

### Step 2: Apply Required Protections in Transformation Step

Following the recommended actions:
1. `student_id` → Apply SHA-256 cryptographic hash
2. `student_email` → Apply partial masking (`s******@example.edu`)
3. `contact_phone` → Apply suffix masking (`********01`)
4. `full_name` → Apply pseudonymization / masking

---

### Step 3: Re-Validate Compliant Dataset

Resubmit the transformed dataset schema to `POST /pipeline/validate` with identical or updated `pipeline_id`:

#### Response (Ready for Publication):
```json
{
  "pipeline_id": "PL-2026-F1A90B",
  "execution_id": "EX-2026-990C11",
  "status": "READY",
  "decision": "ALLOW",
  "policy_status": "PASS",
  "authorization_status": "PASS",
  "risk_level": "LOW",
  "risk_score": 10,
  "policy_violations": [],
  "message": "Pipeline validation PASSED. Dataset is SAFE to publish to University Analytics Warehouse."
}
```

---

### Step 4: Publish to Analytics Warehouse

Execute `POST /pipeline/publish`:

```http
POST /pipeline/publish HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "pipeline_id": "PL-2026-F1A90B",
  "role": "ANALYST",
  "target_destination": "University Analytics Warehouse"
}
```

#### Successful Response:
```json
{
  "pipeline_id": "PL-2026-F1A90B",
  "execution_id": "EX-2026-990C11",
  "status": "PUBLISHED",
  "decision": "ALLOW",
  "success": true,
  "message": "Pipeline dataset successfully published to University Analytics Warehouse.",
  "published_at": "2026-09-29T14:40:00.000Z",
  "audit_reference": "7d9c12e84f50..."
}
```

---

## 4. Batch Validation Endpoint

To validate multiple datasets before an analytical ETL job runs, use `POST /pipeline/batch`:

```http
POST /pipeline/batch HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "batch_id": "BATCH-2026-001",
  "role": "ANALYST",
  "target_destination": "University Analytics Warehouse",
  "datasets": [
    {
      "dataset_name": "course_enrollment.csv",
      "raw_content": "course_id,department,credits\nCS101,Computer Science,4"
    },
    {
      "dataset_name": "student_grades.json",
      "raw_content": "[{\"student_id\":\"STU_001\",\"grade\":\"A\"}]"
    }
  ]
}
```

If **any** dataset contains unmasked sensitive fields, `summary.overall_decision` is `BLOCK` and `fail_closed_triggered` is `true`.

---

## 5. Security & Privacy Guarantees

- **Data Minimization**: The pipeline service retains only schema metadata, field names, inferred types, and cryptographic audit proofs. Raw rows are never persisted to disk or SQLite.
- **Fail-Closed Gate**: Any syntax failure, missing policy, or unmasked sensitive attribute results in an immediate BLOCK.
- **Idempotency**: Providing an existing `execution_id` guarantees deterministic replay without duplicate publication actions.
- **Audit Verification**: Every validation, block, and publication event appends a SHA-256 chained record verifiable via `GET /audit/integrity`.
