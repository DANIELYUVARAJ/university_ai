# University DataShield — Requirements Traceability Matrix

This matrix maps every functional, security, and governance requirement of the University DataShield specification to concrete implementation modules, APIs, and automated test evidence.

| Requirement ID | Requirement Description | Implementation Module | Primary APIs | Test Verification Evidence | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-01** | Automated Sensitive-Field Discovery | `backend/detection/` | `POST /scan`<br>`GET /scan/schema` | `tests/test_detection_engine.py`<br>(37 tests) | **PASS** |
| **REQ-02** | Synthetic Validation Dataset & Baseline Comparison | `backend/baseline/`<br>`backend/evaluation/` | `GET /evaluate`<br>`POST /evaluate` | `tests/test_evaluation_baseline.py`<br>(23 tests) | **PASS** |
| **REQ-03** | Masking Policy Engine (Defaults & Overrides) | `backend/policies/` | `GET /policies`<br>`POST /policies/validate`<br>`POST /policies/preview` | `tests/test_policy_engine.py`<br>(23 tests) | **PASS** |
| **REQ-04** | Role-Based Access Control (5 University Roles) | `backend/access/` | `GET /roles`<br>`GET /roles/{name}` | `tests/test_access_roles.py`<br>(25 tests) | **PASS** |
| **REQ-05** | Publication Gate (Default Deny Enforcement) | `backend/publication/` | `POST /publish-check`<br>`POST /publish` | `tests/test_security_validation.py`<br>`tests/test_phase8_integration.py` | **PASS** |
| **REQ-06** | Complete Audit Trail (Zero PII Logging) | `backend/audit/` | `GET /audit`<br>`GET /audit/integrity` | `tests/test_governance_and_audit.py`<br>(Tests 1–8) | **PASS** |
| **REQ-07** | Cryptographic Tamper-Evident SHA-256 Audit Chain | `backend/audit/` | `GET /audit/integrity` | `tests/test_security_validation.py`<br>(Test 9, 30) | **PASS** |
| **REQ-08** | Policy Change Governance & No Self-Approval | `backend/governance/` | `POST /policies/propose`<br>`POST /policies/approve`<br>`POST /policies/reject` | `tests/test_governance_and_audit.py`<br>(Tests 9–16) | **PASS** |
| **REQ-09** | Immutable Policy Versioning & Diffing | `backend/governance/` | `GET /policies/versions`<br>`GET /policies/diff` | `tests/test_governance_and_audit.py`<br>(Tests 17–20) | **PASS** |
| **REQ-10** | Safe Policy Rollback & Automated Post-Revalidation | `backend/governance/` | `POST /policies/rollback` | `tests/test_governance_and_audit.py`<br>(Tests 21–26) | **PASS** |
| **REQ-11** | End-to-End Adversarial Failure Testing | `backend/security_validation/` | `POST /security-validation/run`<br>`GET /security-validation/results`<br>`GET /security-validation/metrics` | `tests/test_security_validation.py`<br>(30 tests) | **PASS** |
| **REQ-12** | Database Privacy & Zero Raw Personal Data Storage | `backend/database.py` | SQLite inspection | `tests/test_phase8_integration.py`<br>(Test 11)<br>`tests/test_governance_and_audit.py`<br>(Tests 27–30) | **PASS** |
| **REQ-13** | Deterministic Demo Seeding & Environment Reset | `backend/demo/` | `POST /demo/reset`<br>`GET /dashboard/summary` | `tests/test_phase8_integration.py`<br>(Tests 1–4) | **PASS** |
| **REQ-14** | Evaluator Guided User Interface & Dashboard | `frontend/src/` | React 19 UI | Clean production build (`tsc -b && vite build`) | **PASS** |
| **REQ-15** | One-Command System Verification Script | `scripts/` | `verify_final.py`<br>`demo_final_verification.py` | `scripts/verify_final.py`<br>11/11 pillars PASS | **PASS** |
