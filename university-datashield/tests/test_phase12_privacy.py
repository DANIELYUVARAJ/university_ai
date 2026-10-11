"""
Phase 12.7 Automated Tests: Privacy & Data Minimization Regressions
Enforces zero personal data leakage, no unmasked identifiers, and secret exclusion.
"""

import sqlite3
import pytest
from pathlib import Path
from scripts.privacy_audit import run_privacy_audit, audit_active_database, audit_source_tree


def test_privacy_audit_suite_passes():
    """Verify that current codebase has zero privacy or secret violations."""
    report = run_privacy_audit()
    assert report["is_compliant"] is True
    assert report["source_violations_count"] == 0
    assert report["database_violations_count"] == 0


def test_privacy_scanner_detects_synthetic_ssn_leak(tmp_path):
    """Verify that if an unmasked SSN were accidentally written to DB, auditor flags it."""
    test_db = tmp_path / "leaky_test.db"
    conn = sqlite3.connect(str(test_db))
    conn.execute(
        """
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY,
            reason TEXT,
            metadata_json TEXT
        );
        """
    )
    # Insert unmasked SSN in reason
    conn.execute(
        "INSERT INTO audit_events VALUES (1, 'User registered with SSN 456-78-1234', '{}')"
    )
    conn.commit()
    conn.close()

    violations = audit_active_database(test_db)
    assert len(violations) >= 1
    assert violations[0]["rule"] == "real_ssn_unmasked"


def test_privacy_scanner_detects_credit_card_leak(tmp_path):
    """Verify that credit card pattern in pipeline summary triggers audit failure."""
    test_db = tmp_path / "card_test.db"
    conn = sqlite3.connect(str(test_db))
    conn.execute(
        """
        CREATE TABLE pipeline_runs (
            id INTEGER PRIMARY KEY,
            pipeline_id TEXT,
            summary_json TEXT,
            report_markdown TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO pipeline_runs VALUES (1, 'pipe-001', '{\"card\": \"4111111111111111\"}', 'Report')"
    )
    conn.commit()
    conn.close()

    violations = audit_active_database(test_db)
    assert len(violations) >= 1
    assert violations[0]["rule"] == "credit_card_visa_mc"
