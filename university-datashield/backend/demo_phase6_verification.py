"""
Phase 6 End-to-End Live Demonstration Script
Verifies the complete 9-step governance lifecycle against the live backend.
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

print("--- STARTING PHASE 6 DEMONSTRATION SCENARIO ---")

# Step 1: Active policy v1.0, Phone MASK
status, policies = request("GET", "/policies")
print(f"\n[Step 1] Initial Active Policy: version={policies['version']}")
print(f"         Phone Override: {policies['field_overrides'].get('phone')}")
assert policies['field_overrides'].get('phone') == 'MASK', "Step 1 failed: phone override is not MASK"

# Step 2: DATA_ENGINEER proposes phone MASK -> GENERALIZE
prop_payload = {
    "target": "phone",
    "is_field_override": True,
    "proposed_action": "GENERALIZE",
    "reason": "Testing whether generalized contact information can support aggregate cohort analysis.",
    "requested_by_role": "DATA_ENGINEER",
    "requested_by_actor": "engineer-demo",
}
status, prop_res = request("POST", "/policies/propose", prop_payload)
chg_id = prop_res["id"]
print(f"\n[Step 2] DATA_ENGINEER proposed change: id={chg_id}, status={prop_res['status']}")
print(f"         Current: {prop_res['current_version']}, Proposed: {prop_res['proposed_version']}")
assert prop_res["status"] == "PENDING"

# Step 3: Change appears as PENDING, Active policy remains v1.0
status, active_pol = request("GET", "/policies")
print(f"\n[Step 3] Active policy check during pending: version={active_pol['version']}")
print(f"         Phone override remains: {active_pol['field_overrides'].get('phone')}")
assert active_pol['version'] == 'v1.0'
assert active_pol['field_overrides'].get('phone') == 'MASK'

# Step 4: Attempt approval by DATA_ENGINEER (engineer-demo)
status, self_appr = request("POST", "/policies/approve", {
    "change_id": chg_id,
    "reviewed_by_role": "DATA_ENGINEER",
    "reviewed_by_actor": "engineer-demo",
    "review_reason": "Self-approval attempt",
})
print(f"\n[Step 4] Self-approval / Non-admin attempt result: status={status}")
print(f"         Response detail: {self_appr.get('detail')}")
assert status in (403, 409), f"Step 4 failed: unexpected status {status}"

# Step 5: Security Admin approves
status, appr_res = request("POST", "/policies/approve", {
    "change_id": chg_id,
    "reviewed_by_role": "SECURITY_ADMIN",
    "reviewed_by_actor": "security-admin-demo",
    "review_reason": "Approved for testing aggregate statistics",
})
print(f"\n[Step 5] Security Admin approval: status={status}")
print(f"         New active version: {appr_res['version']}, status={appr_res['status']}")
assert appr_res["version"] == "v1.1"

# Step 6: Run publication check - new policy actually used
status, pub_res = request("POST", "/publish-check", {
    "dataset_name": "student_cohort_analysis",
    "role": "ANALYST",
    "fields": [
        {
            "name": "phone",
            "classification": "DIRECT_IDENTIFIER",
            "actual_action": "GENERALIZE",
        }
    ]
})
print(f"\n[Step 6] Publication check under new policy (v1.1):")
print(f"         Policy Version: {pub_res['policy_version']}")
print(f"         Gate Decision: {pub_res['decision']}, Policy Compliant: {pub_res['policy_compliant']}")
assert pub_res["decision"] == "ALLOW", "Step 6 failed: publication check did not ALLOW compliant GENERALIZE action"

# Step 7: Show audit trail
status, audit_events = request("GET", "/audit?limit=6")
print(f"\n[Step 7] Recent Audit Trail Entries ({len(audit_events)} retrieved):")
for ev in audit_events[:4]:
    print(f"         - [{ev['action']}] actor={ev['actor_role']} result={ev['result']} ver={ev['policy_version']} reason={ev['reason'][:50]}...")

# Step 8: Rollback v1.1 to v1.0
status, rollback_res = request("POST", "/policies/rollback", {
    "target_version": "v1.0",
    "actor_role": "SECURITY_ADMIN",
    "actor_id": "security-admin-demo",
    "reason": "Cohort analysis completed; reverting phone to mandatory MASK",
})
print(f"\n[Step 8] Rollback execution:")
print(f"         Resulting active version: {rollback_res['resulting_active_version']}")
print(f"         Target version: {rollback_res['target_version']}")
print(f"         Post-rollback validation: {rollback_res['revalidation_status']}")
assert rollback_res["revalidation_status"] == "PASS"

# Step 9: Verify history preserved & rolled-back behavior
status, vers = request("GET", "/policies/versions")
ver_names = [v["version"] for v in vers]
print(f"\n[Step 9] Historical Version Preservation Check:")
print(f"         All versions in DB: {ver_names}")
assert "v1.0" in ver_names and "v1.1" in ver_names

status, active_after = request("GET", "/policies")
print(f"         Active Policy after rollback: version={active_after['version']}")
print(f"         Phone override restored to: {active_after['field_overrides'].get('phone')}")
assert active_after['field_overrides'].get('phone') == 'MASK'

# Verify integrity
status, integrity = request("GET", "/audit/integrity")
print(f"\n[Integrity Check] SHA-256 Hash Chain: {integrity['status']} ({integrity['events_checked']} events)")
assert integrity['status'] == "VALID"

print("\n--- PHASE 6 DEMONSTRATION SCENARIO COMPLETE: 100% PASS ---")
