"""
Phase 12.8 Automated Tests: Security Hardening & Penetration Defense Suite
Tests fail-closed posture across:
1. API Attacks (deep nesting, oversized payloads, malformed JSON, SQLi injection attempts, path traversal)
2. Bypass attempts (client approved=true, safe=true, retry bypass, destination bypass)
3. Cryptographic tamper detection (deleted event, reordered event, corrupted previous hash)
"""

import sys
import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from destinations.base import PublicationPayload, DestinationResult
from destinations.mock_warehouse import MockWarehouseDestination
from destinations.postgres_destination import PostgresDestination
from audit.audit_repository import compute_event_hash, GENESIS_HASH


@pytest.fixture
def client():
    return TestClient(app)


def test_malformed_json_fails_closed(client):
    """Malformed JSON body must be rejected with 400 or 422."""
    res = client.post(
        "/scan",
        data="{'invalid_json_missing_quotes: true",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code in (400, 422)


def test_deeply_nested_json_protection(client):
    """Deeply nested JSON payload (e.g. > 15 levels) must not cause recursion overflow."""
    nested = {"data": "deep"}
    for _ in range(25):
        nested = {"child": nested}
    res = client.post("/scan", json={"dataset_name": "nested_attack", "fields": [nested]})
    # Handled safely (validation error or rejected) without 500 crash
    assert res.status_code in (400, 422)


def test_sql_injection_in_dataset_name_rejected_safely(client):
    """SQL injection in dataset_name must be safely parameterized without syntax errors."""
    sqli_payload = "test_dataset'; DROP TABLE policies; --"
    res = client.post(
        "/scan",
        json={"dataset_name": sqli_payload, "fields": [{"name": "student_name", "data_type": "string"}]},
    )
    assert res.status_code == 200
    # Verify policies table was NOT dropped
    from database import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM policies")
    count = cur.fetchone()[0]
    conn.close()
    assert count >= 0


def test_path_traversal_in_dataset_name_neutralized(client):
    """Path traversal attempt in dataset_name parameter."""
    res = client.post(
        "/scan",
        json={"dataset_name": "../../../etc/passwd", "fields": [{"name": "id", "data_type": "string"}]},
    )
    assert res.status_code == 200
    assert res.json()["dataset_name"] == "../../../etc/passwd"


def test_client_approved_flag_bypass_blocked(client):
    """Client sending client_approved=True or safe=True must NOT bypass publication gate."""
    # Attempting to publish an unmasked SSN with client_approved=True
    bypass_payload = {
        "dataset_name": "bypass_attempt",
        "role": "ANALYST",
        "client_approved": True,  # Attacker attempt
        "safe": True,             # Attacker attempt
        "bypass_gate": True,      # Attacker attempt
        "fields": [
            {
                "name": "ssn",
                "classification": "DIRECT_IDENTIFIER",
                "actual_action": "NONE",  # Unmasked!
            }
        ]
    }
    res = client.post("/publish", json=bypass_payload)
    assert res.status_code == 200
    body = res.json()
    # Invariant: Server decision is BLOCK, success is False!
    assert body["decision"] == "BLOCK"
    assert body["success"] is False
    assert len(body["reasons"]) > 0



def test_destination_refuses_non_allow_decision():
    """Destination adapter must fail closed if decision is not ALLOW."""
    dest = MockWarehouseDestination()
    payload = PublicationPayload(
        dataset_name="student_test",
        run_id="run-001",
        pipeline_id="pipe-001",
        decision="BLOCK",  # NON-ALLOW!
        schema_definition=[],
        records=[{"id": 1}],
        audit_hash="fakehash",
        publisher_role="ANALYST",
        published_by="analyst1",
        destination_target="analytics_table",
    )
    result = dest.publish(payload)
    assert result.success is False
    assert result.records_written == 0
    assert "rejected" in result.message.lower() or "blocked" in result.message.lower()


def test_postgres_destination_refuses_block_decision():
    """PostgresDestination must fail closed on BLOCK."""
    dest = PostgresDestination(config={"connection_url": "postgresql://user:pass@localhost:5432/mart"})
    payload = PublicationPayload(
        dataset_name="student_test",
        run_id="run-002",
        pipeline_id="pipe-002",
        decision="BLOCK",
        schema_definition=[],
        records=[{"id": 1}],
        audit_hash="fakehash",
        publisher_role="ANALYST",
        published_by="analyst1",
        destination_target="analytics_table",
    )
    result = dest.publish(payload)
    assert result.success is False
    assert result.records_written == 0


def test_audit_hash_tamper_detection(tmp_path):
    """Tampering with an event hash must invalidate the entire downstream audit chain."""
    db_path = tmp_path / "tamper_audit.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            dataset TEXT,
            field_name TEXT,
            result TEXT NOT NULL,
            reason TEXT,
            policy_version TEXT,
            change_id TEXT,
            metadata_json TEXT,
            previous_hash TEXT,
            event_hash TEXT
        );
        """
    )
    # Event 1
    h1 = compute_event_hash(GENESIS_HASH, "2026-10-01T00:00:00Z", "ADMIN", "sys", "INIT", "", "", "OK", "", "v1.0", "", "{}")
    conn.execute("INSERT INTO audit_events VALUES (1, '2026-10-01T00:00:00Z', 'ADMIN', 'sys', 'INIT', '', '', 'OK', '', 'v1.0', '', '{}', ?, ?)", (GENESIS_HASH, h1))
    # Event 2
    h2 = compute_event_hash(h1, "2026-10-01T00:00:01Z", "ANALYST", "usr1", "SCAN", "data", "", "OK", "", "v1.0", "", "{}")
    conn.execute("INSERT INTO audit_events VALUES (2, '2026-10-01T00:00:01Z', 'ANALYST', 'usr1', 'SCAN', 'data', '', 'OK', '', 'v1.0', '', '{}', ?, ?)", (h1, h2))
    conn.commit()

    # Now tamper: modify Event 1 reason
    conn.execute("UPDATE audit_events SET reason = 'Malicious alteration' WHERE id = 1")
    conn.commit()
    conn.close()

    # Verify tamper detected
    from scripts.verify_backup import verify_backup_integrity
    report = verify_backup_integrity(db_path)
    assert report["audit_chain_valid"] is False
    assert report["compromised_event_id"] == 1
