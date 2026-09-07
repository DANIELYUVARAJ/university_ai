# University DataShield — Final Verification & Reproducibility Guide

This guide documents the exact commands and expected outputs for an evaluator to independently verify University DataShield in under five minutes.

---

## 1. Quick Verification Commands

### A. One-Command System Verification
Verifies all 11 operational pillars (Foundation, Detection, Baseline, Masking, RBAC, Gate, Audit, Governance, Rollback, Security, Privacy):

```bash
python scripts/verify_final.py
```

Expected Output:
```text
================================================
 UNIVERSITY DATASHIELD FINAL VERIFICATION
================================================
 Foundation                 PASS
 Detection                  PASS
 Baseline                   PASS
 Masking                    PASS
 RBAC                       PASS
 Publication Gate           PASS
 Audit                      PASS
 Governance                 PASS
 Rollback                   PASS
 Security Validation        PASS
 Privacy                    PASS
================================================
 OVERALL: PASS
================================================
```

---

### B. End-to-End Evaluator Demo Journey
Executes the deterministic 23-step evaluator flow and prints the final scorecard:

```bash
python backend/demo_final_verification.py
```

Expected Outcome: `100% PASS` across all 23 steps, followed by the Final Verification Scorecard.

---

### C. Full Automated Test Suite
Runs all 179 automated unit, integration, governance, and adversarial tests:

```bash
pytest tests/ -v
```

Expected Outcome: `179 passed in ~5s`.

---

### D. Frontend Production Build
Validates strict TypeScript types and compiles Vite production assets:

```bash
cd frontend
npm run build
```

Expected Outcome: `tsc -b && vite build` completes with 0 errors.

---

## 2. Interactive Browser Demonstration

1. Open `http://localhost:5173` in a browser.
2. View the **Executive Dashboard**:
   - Verify live System Status indicators (all green).
   - Observe live metrics from SQLite database.
3. Walk through the **Evaluator Journey**:
   - **Step 1 — Scan**: Go to `/scanner` and scan the built-in synthetic university schema.
   - **Step 2 — Protect**: Go to `/policy-validator` and inspect required masking actions.
   - **Step 3 — Gate**: Go to `/publication-gate` and test an unmasked publication (confirm `BLOCK`), then fix to masked (confirm `ALLOW`).
   - **Step 4 — RBAC**: Switch Demo Role in top header to `FACULTY` and attempt publish (confirm `BLOCK - UNAUTHORIZED`).
   - **Step 5 — Governance**: Go to `/change-review` to propose a change, verify that self-approval is blocked, and approve with `SECURITY_ADMIN`.
   - **Step 6 — Rollback**: Go to `/policy-versions` and execute rollback to `v1.0` (confirm safe post-rollback revalidation).
   - **Step 7 — Security Validation**: Go to `/security-validation` and click "Run Security Validation Suite" (confirm 14 / 14 Passed).
   - **Step 8 — Privacy**: Go to `/privacy` to review automated database inspection proofs.
4. Click **Reset Demo Baseline** on the Dashboard at any time to return the environment to pristine `v1.0`.
