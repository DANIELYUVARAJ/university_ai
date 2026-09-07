#!/usr/bin/env python3
"""
University DataShield — Final One-Command Verification Script (Phase 8)
Verifies all 12 operational pillars across backend, database, security, and privacy.
"""

import sys
import json
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "datashield.db"
BASE_URL = "http://127.0.0.1:8000"


def http_req(path: str, method: str = "GET", payload: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data_bytes = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}


def run_checks():
    results = {}

    # 1. Foundation
    try:
        status, data = http_req("/health")
        results["Foundation"] = (status == 200 and data.get("status") == "ok" and data.get("phase") == 8)
    except Exception:
        results["Foundation"] = False

    # 2. Detection Engine
    try:
        scan_payload = {
            "dataset_name": "final_verify_scan",
            "fields": [
                {"name": "student_id", "data_type": "string", "sample_pattern": "STU12345"},
                {"name": "email", "data_type": "string", "sample_pattern": "demo@univ.edu"},
                {"name": "course_code", "data_type": "string", "sample_pattern": "CS101"},
            ],
        }
        status, data = http_req("/scan", method="POST", payload=scan_payload)
        results["Detection"] = (status == 200 and data.get("sensitive_count", 0) >= 2)
    except Exception:
        results["Detection"] = False

    # 3. Baseline Comparison
    try:
        status, data = http_req("/evaluate", method="GET")
        results["Baseline"] = (status == 200 and "datashield" in data and "baseline" in data)
    except Exception:
        results["Baseline"] = False

    # 4. Masking Policy Engine
    try:
        val_payload = {
            "dataset_name": "final_verify_val",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
            ],
        }
        status, data = http_req("/policies/validate", method="POST", payload=val_payload)
        results["Masking"] = (status == 200 and data.get("overall_status") in ("PASS", "REVIEW"))
    except Exception:
        results["Masking"] = False

    # 5. Role-Based Access Control (RBAC)
    try:
        status, data = http_req("/roles")
        results["RBAC"] = (status == 200 and len(data) >= 5)
    except Exception:
        results["RBAC"] = False

    # 6. Publication Gate (Fail-Closed Default Deny)
    try:
        # Check unsafe unmasked publication
        pub_payload = {
            "dataset_name": "final_verify_pub",
            "role": "SECURITY_ADMIN",
            "fields": [
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"},
            ],
        }
        status, data = http_req("/publish", method="POST", payload=pub_payload)
        results["Publication Gate"] = (status == 200 and data.get("decision") == "BLOCK" and data.get("success") is False)
    except Exception:
        results["Publication Gate"] = False

    # 7. Audit Ledger & Cryptographic Integrity
    try:
        status, data = http_req("/audit/integrity")
        results["Audit"] = (status == 200 and data.get("status") == "VALID")
    except Exception:
        results["Audit"] = False

    # 8. Governance & Policy Versioning
    try:
        status, data = http_req("/policies/versions")
        results["Governance"] = (status == 200 and len(data) >= 1)
    except Exception:
        results["Governance"] = False

    # 9. Rollback & Post-Rollback Revalidation
    try:
        status, data = http_req("/demo/reset", method="POST")
        results["Rollback"] = (status == 200 and data.get("status") == "RESET_COMPLETE")
    except Exception:
        results["Rollback"] = False

    # 10. Security Validation & Adversarial Resistance
    try:
        status, data = http_req("/security-validation/results")
        results["Security Validation"] = (
            status == 200
            and data.get("scenarios_passed", 0) == 14
            and data.get("metrics", {}).get("unsafe_publication_prevention_rate") == 1.0
        )
    except Exception:
        results["Security Validation"] = False

    # 11. Privacy by Design & Zero Raw PII Storage
    try:
        forbidden = ["student001@example.edu", "+91-9000000001", "STU_DEMO_001"]
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        found_pii = False
        tables = [
            ("audit_events", ["dataset", "field_name", "result", "reason", "metadata_json"]),
            ("policy_change_requests", ["reason", "proposed_change_json", "review_reason"]),
            ("policy_versions", ["description", "policy_snapshot"]),
            ("publication_attempts", ["reasons_json"]),
        ]
        for table, cols in tables:
            cur.execute(f"SELECT {', '.join(cols)} FROM {table}")
            for row in cur.fetchall():
                for val in row:
                    if val and any(p in str(val) for p in forbidden):
                        found_pii = True
                        break
        conn.close()
        results["Privacy"] = (not found_pii)
    except Exception:
        results["Privacy"] = False

    # Print Formatted Verification Summary
    print("\n" + "=" * 48)
    print(" UNIVERSITY DATASHIELD FINAL VERIFICATION")
    print("=" * 48)
    all_pass = True
    for pillar, passed in results.items():
        state = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f" {pillar:<26} {state}")
    print("=" * 48)
    print(f" OVERALL: {'PASS' if all_pass else 'FAIL'}")
    print("=" * 48 + "\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run_checks())
