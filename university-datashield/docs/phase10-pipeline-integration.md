# Phase 10 Architecture & Implementation Report: Real Analytical Pipeline Integration & Automation

## 1. Executive Summary

Phase 10 transforms **University DataShield** from a standalone security validation and audit suite into an **integratable, fail-closed analytical pipeline security gate**.

Prior to Phase 10, sensitive field discovery, masking policy validation, and publication gating were invoked via manual testing or direct API checks. Phase 10 introduces:
- **Safe Synthetic Dataset Ingestion**: Ingests raw CSV and JSON payloads, infers schema and basic types, extracts representative pattern samples, and discards raw rows immediately (strict data minimization).
- **Dedicated Analytical Pipeline Service (`backend/pipeline/`)**: Orchestrates schema extraction, sensitive-field detection, masking policy validation, role authorization, and the fail-closed publication gate.
- **Fail-Closed Gate Enforcement**: Client assertions (`client_approved=true`) are strictly ignored. The backend revalidates all requirements independently.
- **Idempotency & Safe Retry Semantics**: Repeated requests with identical execution keys return deterministic cached records. Retries with unchanged unmasked data remain blocked.
- **Fail-Closed Batch Validation**: Evaluates multiple datasets with an aggregate decision that blocks the batch if any dataset fails compliance.
- **Automated Masking Previews**: Generates synthetic previews of required transformations (e.g. SHA-256 for HASH, partial redaction for MASK, year extraction for GENERALIZE).
- **Cryptographic Audit Chaining**: All pipeline lifecycle operations append tamper-evident SHA-256 chained events.
- **Executive Frontend Pipeline Monitor**: Real-time KPI cards, interactive pipeline runner, masking preview table, batch executor, and execution ledger.

---

## 2. Pipeline State Machine

Every pipeline execution follows deterministic, monotonic state transitions:

```text
  [CREATED]
      ↓
  [SCANNING] ──(corrupt CSV/JSON payload)──→ [FAILED]
      ↓
  [DETECTED]
      ↓
[VALIDATING_POLICY] ──(unmasked sensitive fields)──→ [BLOCKED]
      ↓
[VALIDATING_ACCESS] ──(unauthorized role)──────────→ [BLOCKED]
      ↓
   [READY]
      ↓
  [PUBLISHED]
```

### State Definitions:
1. `CREATED`: Request received, execution identifier allocated.
2. `SCANNING`: Parsing CSV/JSON syntax, extracting schema and data types.
3. `DETECTED`: Phase 9 sensitive-field discovery and risk scoring completed.
4. `VALIDATING_POLICY`: Comparing actual transformations against required policies.
5. `VALIDATING_ACCESS`: Checking role against Role-Permission matrix.
6. `READY`: Dataset is fully compliant and authorized for publication.
7. `BLOCKED`: Fail-closed gate engaged; unmasked sensitive data or unauthorized role.
8. `PUBLISHED`: Verified publication to downstream analytical destination completed.
9. `FAILED`: Ingestion syntax error, corrupt payload, or unrecoverable error.

---

## 3. Endpoints Implemented

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/pipeline/validate` | Validates dataset schema, detection, policy, and RBAC |
| `POST` | `/pipeline/preview` | Returns masking previews and recommended actions |
| `POST` | `/pipeline/publish` | Revalidates backend-side and publishes if compliant |
| `POST` | `/pipeline/batch` | Validates multiple datasets with fail-closed summary |
| `GET` | `/pipeline/runs` | Lists recent pipeline execution runs from SQLite |
| `GET` | `/pipeline/{id}` | Retrieves execution details of a specific pipeline |
| `GET` | `/pipeline/{id}/status` | Returns current state machine status of a run |
| `GET` | `/pipeline/{id}/report` | Generates machine-readable JSON and human-readable Markdown |

---

## 4. Performance Benchmarks

Measured on synthetic analytical datasets on Windows x86_64:

| Dataset Size | Columns | CSV Ingest | JSON Ingest | Detection & Risk | Policy Validation | End-to-End Gate (inc. Audit) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **100 rows** | 8 | 0.98 ms | 0.51 ms | 1.76 ms | 0.14 ms | **25.62 ms** |
| **500 rows** | 8 | 2.53 ms | 2.14 ms | 0.93 ms | 0.13 ms | **25.97 ms** |
| **1,000 rows** | 8 | 5.16 ms | 3.25 ms | 0.95 ms | 0.11 ms | **27.89 ms** |

*Note: All latency figures include SQLite write operations and SHA-256 cryptographic audit hash computation.*

---

## 5. Security & Privacy Guarantees

1. **Zero Raw PII Storage**: SQLite table `pipeline_runs` stores strictly metadata, schemas, summary risk scores, violation reasons, and Markdown reports. Raw values are discarded immediately from memory after ingestion.
2. **Re-Validation on Publication**: Calling `/pipeline/publish` re-runs the entire publication check independently. A client-side `client_approved=true` assertion is never trusted.
3. **Fail-Closed Batching**: In batch validation, if 9 out of 10 datasets are safe and 1 is unmasked, the entire batch status is `BLOCK`.
4. **Audit Trail Immutability**: All pipeline outcomes append to the continuous SHA-256 audit ledger with genesis chaining.

---

## 6. Known Limitations & Next Steps

- **Prototype Scope**: Dataset ingestion currently handles CSV and JSON formats in-memory. Binary formats (Parquet, ORC, Avro) are planned for Phase 11.
- **Destination Mocking**: Destination publication simulates release to downstream analytical warehouses (Snowflake, BigQuery, S3).
- **Recommended Next Phase**: **Phase 11 — Production Security, Scalability & Cloud Deployment**.
