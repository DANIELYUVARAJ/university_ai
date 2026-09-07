# University DataShield — Final Experimental & Security Evaluation Results

## 1. Detection Engine vs. Keyword Baseline Benchmark (Phase 3 & Phase 7)

Evaluation was performed against the synthetic ground-truth benchmark dataset comprising 52 representative academic, institutional, and personal fields.

| Metric | Phase 3 Keyword Baseline | University DataShield | Improvement / Advantage |
| :--- | :---: | :---: | :---: |
| **Precision** | 70.0% | **100.0%** | **+30.0%** |
| **Recall** | 58.3% | **75.0%** | **+16.7%** |
| **F1 Score** | 63.6% | **85.7%** | **+22.1%** |
| **Accuracy** | 53.8% | **84.6%** | **+30.8%** |
| **False Positives** | 3 | **0** | **-3 (Zero false blocks on research fields)** |
| **False Negatives** | 5 | **3** | **-2** |
| **Unsafe Publication Prevention** | *N/A (Detection only)* | **100.0%** | **Authoritative Gate Enforcement** |

*Note on Keyword Baseline*: The baseline was intentionally implemented as a simple keyword matching algorithm without contextual semantics, type awareness, or publication gating.

---

## 2. Security & Publication Safety Scorecard (Phase 7 & Phase 8)

Measured across 14 deterministic adversarial failure and edge-case scenarios:

| Security Metric | Definition | Measured Value | Target | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Unsafe Publication Prevention Rate** | Blocked unsafe cases / Total unsafe cases | **100.0%** (9/9) | 100% | **PASS** |
| **Unauthorized Attempt Block Rate** | Blocked unauthorized roles / Total unauthorized attempts | **100.0%** (2/2) | 100% | **PASS** |
| **Audit Coverage Rate** | Audited security events / Expected security events | **100.0%** (14/14) | 100% | **PASS** |
| **Rollback Recovery Rate** | Restored & revalidated safe policies / Rollback scenarios | **100.0%** (1/1) | 100% | **PASS** |
| **False Block Rate** | Safe cases blocked / Total safe cases | **0.0%** (0/2) | < 5% | **PASS** |
| **Safe Publication Rate** | Safe cases allowed / Total safe cases | **100.0%** (2/2) | 100% | **PASS** |
| **Audit Integrity Detection Rate** | Cryptographically caught tampered hashes / Tamper scenarios | **100.0%** (1/1) | 100% | **PASS** |

---

## 3. Database Privacy & Zero Raw PII Inspection

Direct SQLite column regex inspection across:
- `audit_events`
- `policy_change_requests`
- `policy_versions`
- `publication_attempts`

**Result**: Zero occurrences of synthetic test tokens (`student001@example.edu`, `+91-9000000001`, `STU_DEMO_001`, `STU12345`, `demo@univ.edu`, `+91-9876543210`). All stored records contain schema metadata, transformation categories, and SHA-256 hashes only.

---

## 4. Automated Regression Test Suite

- **Total Automated Tests**: 179 / 179 passing cleanly (`pytest tests/ -v` in 5.28s).
  - Phase 1 & 2 (Discovery): 37 tests
  - Phase 3 (Baseline & Metrics): 23 tests
  - Phase 4 (Masking Policies): 23 tests
  - Phase 5 (RBAC & Gate): 25 tests
  - Phase 6 (Audit & Governance): 30 tests
  - Phase 7 (Adversarial Security): 30 tests
  - Phase 8 (Integration & Demo): 11 tests
- **Frontend Production Build**: Clean build in 1.21s with zero TypeScript or bundling errors (`tsc -b && vite build`).
