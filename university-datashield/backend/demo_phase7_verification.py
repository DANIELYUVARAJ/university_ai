"""
Phase 7 End-to-End Live Demonstration & Verification Script
Automated Security Validation, Adversarial Attack Resistance, and Audit Verification.
"""

import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if body else {}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        err_body = json.loads(err.read().decode("utf-8"))
        return err.status, err_body

print("================================================================================")
print("   UNIVERSITY DATASHIELD — PHASE 7 SECURITY & ADVERSARIAL VALIDATION DEMO      ")
print("================================================================================")

# 1. Health & Service check
status, health = request("GET", "/health")
print(f"\n[1] Backend Service Liveness: version={health['version']}, phase={health['phase']}, db={health['database']['ok']}")
assert health["phase"] == 7, "Expected Phase 7"

# 2. Scan synthetic schema & detect sensitive fields
status, scan_res = request("POST", "/scan", {
    "dataset_name": "synthetic_admission_records",
    "fields": [
        {"name": "student_name", "data_type": "string", "sample_pattern": "Alice Smith"},
        {"name": "phone", "data_type": "string", "sample_pattern": "+91-9876543210"},
        {"name": "gpa", "data_type": "float", "sample_pattern": "3.92"},
        {"name": "department", "data_type": "string", "sample_pattern": "Bioengineering"},
    ]
})
print(f"[2] Schema Scan Discovery: {scan_res['fields_scanned']} fields scanned, {scan_res['sensitive_count']} sensitive fields discovered")
assert scan_res["sensitive_count"] >= 2

# 3. Adversarial Attempt: Unmasked direct identifier publication
status, pub_unsafe = request("POST", "/publish-check", {
    "dataset_name": "adversarial_unmasked_leak",
    "role": "ANALYST",
    "fields": [
        {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
    ]
})
print(f"\n[3] Adversarial Test — Unmasked Direct Identifier:")
print(f"    Gate Decision: {pub_unsafe['decision']} (Status: {pub_unsafe['status']})")
print(f"    Reason: {pub_unsafe['reasons'][0] if pub_unsafe['reasons'] else ''}")
assert pub_unsafe["decision"] == "BLOCK"

# 4. Adversarial Attempt: Unauthorized role publication attempt
status, pub_unauth = request("POST", "/publish", {
    "dataset_name": "adversarial_unauthorized_role",
    "role": "FACULTY",
    "target_destination": "public_lake",
    "fields": [
        {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"}
    ]
})
print(f"\n[4] Adversarial Test — Unauthorized Role Publication Gate:")
print(f"    Gate Decision: {pub_unauth['decision']} (Status: {pub_unauth['status']})")
assert pub_unauth["decision"] == "BLOCK"
assert pub_unauth["status"] == "UNAUTHORIZED"

# 5. Adversarial Attempt: Client-side forged approval bypass
status, pub_bypass = request("POST", "/publish", {
    "dataset_name": "adversarial_forged_flags",
    "role": "ANALYST",
    "target_destination": "analytics_dw",
    "approved": True,
    "safe": True,
    "validation_status": "PASS",
    "fields": [
        {"name": "student_name", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
    ]
})
print(f"\n[5] Adversarial Test — Client-Side Flag Injection Bypass:")
print(f"    Gate Decision: {pub_bypass['decision']} (Status: {pub_bypass['status']})")
assert pub_bypass["decision"] == "BLOCK"
assert pub_bypass["success"] is False

# 6. Compliant Publication Verification
status, pub_safe = request("POST", "/publish", {
    "dataset_name": "compliant_analytics_release",
    "role": "ANALYST",
    "target_destination": "secure_analytics_warehouse",
    "fields": [
        {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
        {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
        {"name": "date_of_birth", "classification": "QUASI_IDENTIFIER", "actual_action": "GENERALIZE"},
        {"name": "major", "classification": "NON_SENSITIVE", "actual_action": "NONE"},
    ]
})
print(f"\n[6] Legitimate Compliant Analytics Publication:")
print(f"    Gate Decision: {pub_safe['decision']} (Success: {pub_safe['success']})")
assert pub_safe["decision"] == "ALLOW"
assert pub_safe["success"] is True

# 7. Fail-Closed Verification: Missing policy for sensitive field
status, pub_missing = request("POST", "/publish-check", {
    "dataset_name": "sensitive_unconfigured_field",
    "role": "ANALYST",
    "fields": [
        {"name": "biometric_vector", "classification": "UNKNOWN_SENSITIVE", "actual_action": "NONE"}
    ]
})
print(f"\n[7] Fail-Closed Principle — Missing Policy on Sensitive Field:")
print(f"    Gate Decision: {pub_missing['decision']} (Status: {pub_missing['status']})")
assert pub_missing["decision"] == "BLOCK"

# 8. Cryptographic Audit Integrity Verification
status, integrity = request("GET", "/audit/integrity")
print(f"\n[8] Tamper-Evidence Verification:")
print(f"    SHA-256 Hash Chain: {integrity['status']} ({integrity['events_checked']} events verified)")
assert integrity["status"] == "VALID"

# 9. Execute Full Security Validation Suite
print(f"\n[9] Running Comprehensive Security Validation Suite...")
status, sec_report = request("POST", "/security-validation/run")
m = sec_report["metrics"]
print(f"    Overall Status: {sec_report['overall_status']}")
print(f"    Scenarios: {sec_report['scenarios_passed']} / {sec_report['scenarios_total']} Passed")
print(f"    Unsafe Publication Prevention: {m['unsafe_publication_prevention_rate'] * 100:.1f}%")
print(f"    Unauthorized Block Rate:       {m['unauthorized_block_rate'] * 100:.1f}%")
print(f"    Audit Coverage:                {m['audit_coverage_rate'] * 100:.1f}%")
print(f"    Rollback Recovery Rate:        {m['rollback_recovery_rate'] * 100:.1f}%")
print(f"    False Block Rate:              {m['false_block_rate'] * 100:.1f}%")
print(f"    Privacy (Zero Raw PII in DB):  {'PASS' if sec_report['privacy_check_passed'] else 'FAIL'}")

assert sec_report["overall_status"] == "PASS"
assert m["unsafe_publication_prevention_rate"] == 1.0
assert m["unauthorized_block_rate"] == 1.0
assert sec_report["privacy_check_passed"] is True

print("\n================================================================================")
print("   PHASE 7 SECURITY VALIDATION & ADVERSARIAL TESTING COMPLETED: 100% PASS       ")
print("================================================================================")
