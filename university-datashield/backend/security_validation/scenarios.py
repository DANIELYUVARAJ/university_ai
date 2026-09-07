# backend/security_validation/scenarios.py
"""
Definitions and executable fixtures for realistic Phase 7 security validation scenarios.
All scenarios use deterministic synthetic schemas and values.
"""

from __future__ import annotations
from typing import List, Dict, Any
from .schemas import (
    ScenarioCategory,
    SecuritySeverity,
)

SECURITY_SCENARIO_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "scenario_id": "SEC-01",
        "name": "Compliant Publication Approval",
        "category": ScenarioCategory.PUBLICATION_SAFETY,
        "severity": SecuritySeverity.LOW,
        "description": "Legitimate analytical dataset with all sensitive fields correctly protected according to policy.",
        "attempted_action": "Publish dataset to analytical warehouse by authorized ANALYST.",
        "expected_decision": "ALLOW",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "student_id",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "HASH",
                "sample_value": "STU_DEMO_001",
            },
            {
                "name": "email",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "MASK",
                "sample_value": "student001@example.edu",
            },
            {
                "name": "date_of_birth",
                "classification": "QUASI_IDENTIFIER",
                "actual_action": "GENERALIZE",
                "sample_value": "2002-04-15",
            },
            {
                "name": "major",
                "classification": "NON_SENSITIVE",
                "actual_action": "NONE",
                "sample_value": "Data Science",
            },
        ],
        "expected_audit": "PUBLICATION",
    },
    {
        "scenario_id": "SEC-02",
        "name": "Unmasked Direct Identifier Block",
        "category": ScenarioCategory.PUBLICATION_SAFETY,
        "severity": SecuritySeverity.CRITICAL,
        "description": "Attempt to publish dataset with unprotected phone number (actual: NONE, required: MASK).",
        "attempted_action": "Publish dataset containing raw direct identifier without protection.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "phone",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "NONE",
                "sample_value": "+91-9000000001",
            },
            {
                "name": "department",
                "classification": "NON_SENSITIVE",
                "actual_action": "NONE",
                "sample_value": "Engineering",
            },
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-03",
        "name": "Unauthorized Role Publication Gate Denial",
        "category": ScenarioCategory.ACCESS_CONTROL,
        "severity": SecuritySeverity.HIGH,
        "description": "Role without PUBLISH permission (FACULTY) attempts publication to external destination.",
        "attempted_action": "Publication attempt by FACULTY role.",
        "expected_decision": "BLOCK",
        "role": "FACULTY",
        "synthetic_fields": [
            {
                "name": "student_id",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "HASH",
                "sample_value": "STU_DEMO_002",
            }
        ],
        "expected_audit": "ACCESS_DENIAL",
    },
    {
        "scenario_id": "SEC-04",
        "name": "Client-Side Flag Injection / Bypass Attempt",
        "category": ScenarioCategory.BYPASS_RESISTANCE,
        "severity": SecuritySeverity.CRITICAL,
        "description": "Request injects forged approval flags (approved=True, safe=True, status=PASS) while raw personal name is unprotected.",
        "attempted_action": "Adversarial publication check with forged client-side compliance metadata.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "forged_client_flags": {
            "approved": True,
            "safe": True,
            "validation_status": "PASS",
            "pre_approved_by": "SECURITY_ADMIN",
        },
        "synthetic_fields": [
            {
                "name": "student_name",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "NONE",
                "sample_value": "Demo Student",
            }
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-05",
        "name": "Wrong Masking Transformation Mismatch",
        "category": ScenarioCategory.MASKING_COMPLIANCE,
        "severity": SecuritySeverity.HIGH,
        "description": "Email address requires MASK protection; transformation applied is GENERALIZE (insufficient protection).",
        "attempted_action": "Publish with mismatched transformation that fails specific required policy.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "email",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "GENERALIZE",
                "sample_value": "student@example.edu",
            }
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-06",
        "name": "Missing Policy Fail-Closed Behavior",
        "category": ScenarioCategory.FAIL_CLOSED_BEHAVIOR,
        "severity": SecuritySeverity.CRITICAL,
        "description": "Sensitive field with undefined or conflicting classification; system must fail closed rather than publish.",
        "attempted_action": "Validate and publish field with undefined classification policy.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "restricted_health_biometric",
                "classification": "UNKNOWN_SENSITIVE",
                "actual_action": "NONE",
                "sample_value": "BIO_SYNTH_999",
            }
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-07",
        "name": "Ambiguous Field Name Multi-Signal Resolution",
        "category": ScenarioCategory.PUBLICATION_SAFETY,
        "severity": SecuritySeverity.HIGH,
        "description": "Field named 'contact' (ambiguous name) with phone number regex pattern. Engine uses value pattern to catch sensitive data.",
        "attempted_action": "Discovery and unmasked publication of ambiguous contact field.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "contact",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "NONE",
                "sample_value": "+1-555-0199",
            }
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-08",
        "name": "False-Positive Trap Resistance",
        "category": ScenarioCategory.FALSE_POSITIVE_RESISTANCE,
        "severity": SecuritySeverity.LOW,
        "description": "Legitimate non-sensitive analytical aggregates (email_template_id, course_code, student_count) are not falsely blocked.",
        "attempted_action": "Publish analytical summary containing aggregate and template columns.",
        "expected_decision": "ALLOW",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "email_template_id",
                "classification": "NON_SENSITIVE",
                "actual_action": "NONE",
                "sample_value": "TMPL_ORIENTATION_2026",
            },
            {
                "name": "course_code",
                "classification": "NON_SENSITIVE",
                "actual_action": "NONE",
                "sample_value": "CS101",
            },
            {
                "name": "student_count",
                "classification": "NON_SENSITIVE",
                "actual_action": "NONE",
                "sample_value": "45",
            },
        ],
        "expected_audit": "PUBLICATION",
    },
    {
        "scenario_id": "SEC-09",
        "name": "Tampered Audit Log Cryptographic Detection",
        "category": ScenarioCategory.AUDIT_INTEGRITY,
        "severity": SecuritySeverity.CRITICAL,
        "description": "Audit trail record has forged metadata or modified event hash; integrity verification catches tampering.",
        "attempted_action": "Simulate modification of historical audit record and run GET /audit/integrity.",
        "expected_decision": "COMPROMISED",
        "role": "SECURITY_ADMIN",
        "synthetic_fields": [],
        "expected_audit": "AUDIT_INTEGRITY",
    },
    {
        "scenario_id": "SEC-10",
        "name": "Bad Policy Rollback & Safe Revalidation",
        "category": ScenarioCategory.POLICY_LIFECYCLE,
        "severity": SecuritySeverity.HIGH,
        "description": "Unsafe policy change is proposed; Security Admin rolls back to baseline v1.0 snapshot; automatic revalidation runs.",
        "attempted_action": "Execute rollback of degraded policy snapshot with automated post-rollback validation.",
        "expected_decision": "ALLOW",
        "role": "SECURITY_ADMIN",
        "synthetic_fields": [],
        "expected_audit": "POLICY_ROLLBACK",
    },
    {
        "scenario_id": "SEC-11",
        "name": "Malformed Value on Sensitive Field (Name Precedence)",
        "category": ScenarioCategory.FAIL_CLOSED_BEHAVIOR,
        "severity": SecuritySeverity.HIGH,
        "description": "Phone field with non-standard value ('not-a-phone'); system relies on field name rule rather than silently treating as safe.",
        "attempted_action": "Attempt to bypass discovery using corrupted synthetic phone string.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "phone",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "NONE",
                "sample_value": "not-a-phone",
            }
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-12",
        "name": "Null/Empty Value on Direct Identifier",
        "category": ScenarioCategory.FAIL_CLOSED_BEHAVIOR,
        "severity": SecuritySeverity.HIGH,
        "description": "Email column with null/empty sample values; schema sensitivity still requires protection if published.",
        "attempted_action": "Attempt to publish unmasked email column with null sample values.",
        "expected_decision": "BLOCK",
        "role": "ANALYST",
        "synthetic_fields": [
            {
                "name": "email",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "NONE",
                "sample_value": None,
            }
        ],
        "expected_audit": "PUBLICATION_CHECK",
    },
    {
        "scenario_id": "SEC-13",
        "name": "API-Level Privilege Escalation Bypass on Rollback",
        "category": ScenarioCategory.ACCESS_CONTROL,
        "severity": SecuritySeverity.HIGH,
        "description": "DATA_ENGINEER attempts direct POST /policies/rollback; backend rejects with 403 GOVERNANCE_ROLE_REQUIRED.",
        "attempted_action": "Invoke policy rollback with non-admin actor role.",
        "expected_decision": "BLOCK",
        "role": "DATA_ENGINEER",
        "synthetic_fields": [],
        "expected_audit": "ACCESS_DENIAL",
    },
    {
        "scenario_id": "SEC-14",
        "name": "Self-Approval Policy Change Block",
        "category": ScenarioCategory.ACCESS_CONTROL,
        "severity": SecuritySeverity.HIGH,
        "description": "Proposer attempts to approve their own policy proposal; backend rejects with 409 SELF_APPROVAL_BLOCKED.",
        "attempted_action": "Attempt self-approval of change request.",
        "expected_decision": "BLOCK",
        "role": "SECURITY_ADMIN",
        "synthetic_fields": [],
        "expected_audit": "POLICY_CHANGE_PROPOSED",
    },
]
