# University DataShield — Evaluator User Journey & Operational Flows

## 1. Primary Analytics Release Journey

```text
[1. Scan Schema]
   Evaluator opens Dataset Scanner (/scanner)
   ↓ Uploads / selects synthetic university schema (student_id, email, phone, course_code, etc.)
   ↓ Detection engine extracts 4 signals (Name regex, Pattern regex, Data Type, Semantics)
   ↓ Explainable classification output: Direct Identifier, Quasi-Identifier, Academic Data, Non-Sensitive

[2. Review & Protect]
   Evaluator reviews required protection actions (/policy-validator)
   ↓ student_id → HASH
   ↓ email → MASK
   ↓ phone → MASK
   ↓ date_of_birth → GENERALIZE
   ↓ course_code → NONE
   ↓ Previews deterministic masking transformation output

[3. Gate Enforcement: Unsafe Attempt]
   Evaluator tests publication gate (/publication-gate) with an unmasked field (e.g. phone: NONE)
   ↓ Publication Gate independently evaluates payload against active policy v1.0
   ↓ Outcome: BLOCK (Status: PUBLICATION_BLOCKED)
   ↓ Explainable rejection reason displayed; event logged to audit trail

[4. Fix & Compliant Release]
   Evaluator updates phone protection to MASK
   ↓ Publication Gate re-evaluates role permissions and policy compliance
   ↓ Outcome: ALLOW (Status: SAFE_TO_PUBLISH)
   ↓ Analytical export released safely; event logged to audit trail

[5. Role-Based Access Boundary Check]
   Evaluator switches demo role to FACULTY (role lacking publication privileges)
   ↓ Attempts publication of compliant dataset
   ↓ Outcome: BLOCK (Status: UNAUTHORIZED)
   ↓ Backend gate strictly enforces RBAC regardless of data compliance
```

---

## 2. Policy Governance & Safe Rollback Flow

```text
[1. Propose Change]
   Data Engineer proposes weakening or altering a rule (e.g. phone: MASK -> GENERALIZE)
   ↓ Request is held in PENDING status; active policy v1.0 remains unaltered

[2. Separation of Duties Check]
   Proposer attempts to approve their own change request
   ↓ System blocks action: 409 SELF_APPROVAL_BLOCKED
   ↓ Proposer cannot serve as reviewer

[3. Security Admin Review & Approval]
   Security Admin reviews rationale and proposed diff (/change-review)
   ↓ Approves change request
   ↓ System automatically creates new immutable version (v1.1) and marks it ACTIVE
   ↓ Previous version (v1.0) is marked SUPERSEDED

[4. Audit Trail Verification]
   Evaluator inspects Audit Trail (/audit-trail)
   ↓ Verifies complete sequence: POLICY_CHANGE_PROPOSED -> POLICY_APPROVED
   ↓ Verifies SHA-256 cryptographic hash chain integrity: VALID

[5. Safe Rollback with Post-Revalidation]
   Security Admin discovers degraded protection and initiates rollback to v1.0 (/policy-versions)
   ↓ System creates an explicit rollback snapshot (e.g. v1.2-rollback) restoring v1.0 rules
   ↓ Historical version v1.1 remains preserved (history cannot be deleted or mutated)
   ↓ Automated post-rollback revalidation executes against synthetic benchmark (Status: PASS)
   ↓ Publication gate returns to safe baseline protection state
```

---

## 3. Adversarial Validation Suite Flow

```text
Evaluator opens Security Validation (/security-validation)
↓ Clicks "Run Security Validation Suite"
↓ Executes 14 deterministic adversarial failure and edge-case scenarios:
   - SEC-01: Compliant Publication (ALLOW)
   - SEC-02: Unmasked Direct Identifier (BLOCK)
   - SEC-03: Unauthorized Role Publication (BLOCK)
   - SEC-04: Client-Side Approval Flag Bypass (BLOCK)
   - SEC-05: Wrong Masking Transformation (BLOCK)
   - SEC-06: Missing Policy Fail-Closed Default (BLOCK)
   - SEC-07: Ambiguous Field Name with Sensitive Value (BLOCK)
   - SEC-08: False-Positive Trap Resistance (ALLOW)
   - SEC-09: Cryptographic Audit Tampering Detection (INVALID)
   - SEC-10: Bad Policy Rollback & Revalidation (RESTORED)
   - SEC-11: Malformed Value with Sensitive Name (BLOCK)
   - SEC-12: Null Value on Sensitive Field (BLOCK)
   - SEC-13: Privilege Escalation Attempt on Rollback (BLOCK)
   - SEC-14: Self-Approval Attempt (BLOCK)
↓ Displays 100% Unsafe Publication Prevention and cryptographic chain verification
```
