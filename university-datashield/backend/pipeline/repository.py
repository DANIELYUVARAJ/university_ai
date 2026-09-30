# backend/pipeline/repository.py
"""
Persistence repository for analytical pipeline runs in SQLite.
Enforces zero raw PII retention: only stores metadata, risk metrics,
validation state, decisions, and explainability artifacts.
"""

from __future__ import annotations
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from database import get_db


class PipelineRepository:
    @staticmethod
    async def create_or_update_run(
        pipeline_id: str,
        execution_id: str,
        dataset_name: str,
        format_type: str,
        status: str,
        risk_level: str,
        risk_score: int,
        fields_count: int,
        sensitive_count: int,
        violations_count: int,
        decision: str,
        role: str,
        policy_version: str,
        target_destination: str,
        summary_dict: Dict[str, Any],
        report_markdown: Optional[str] = None,
        audit_reference: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """Insert or update a pipeline validation run."""
        summary_json = json.dumps(summary_dict)
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO pipeline_runs (
                    pipeline_id, execution_id, dataset_name, format, status,
                    risk_level, risk_score, fields_count, sensitive_count, violations_count,
                    decision, role, policy_version, target_destination, summary_json,
                    report_markdown, audit_reference, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pipeline_id) DO UPDATE SET
                    execution_id = excluded.execution_id,
                    status = excluded.status,
                    risk_level = excluded.risk_level,
                    risk_score = excluded.risk_score,
                    fields_count = excluded.fields_count,
                    sensitive_count = excluded.sensitive_count,
                    violations_count = excluded.violations_count,
                    decision = excluded.decision,
                    role = excluded.role,
                    policy_version = excluded.policy_version,
                    target_destination = excluded.target_destination,
                    summary_json = excluded.summary_json,
                    report_markdown = excluded.report_markdown,
                    audit_reference = excluded.audit_reference,
                    completed_at = excluded.completed_at
                """,
                (
                    pipeline_id,
                    execution_id,
                    dataset_name,
                    format_type,
                    status,
                    risk_level,
                    risk_score,
                    fields_count,
                    sensitive_count,
                    violations_count,
                    decision,
                    role,
                    policy_version,
                    target_destination,
                    summary_json,
                    report_markdown,
                    audit_reference,
                    completed_at,
                ),
            )
            await db.commit()
        finally:
            await db.close()

    @staticmethod
    async def get_by_pipeline_id(pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve run by its unique pipeline identifier."""
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                SELECT id, pipeline_id, execution_id, dataset_name, format, status,
                       risk_level, risk_score, fields_count, sensitive_count, violations_count,
                       decision, role, policy_version, target_destination, summary_json,
                       report_markdown, audit_reference, created_at, completed_at
                FROM pipeline_runs
                WHERE pipeline_id = ?
                """,
                (pipeline_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["summary"] = json.loads(res["summary_json"])
            except Exception:
                res["summary"] = {}
            return res
        finally:
            await db.close()

    @staticmethod
    async def get_by_execution_id(execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve run by its execution identifier (for idempotency checks)."""
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                SELECT id, pipeline_id, execution_id, dataset_name, format, status,
                       risk_level, risk_score, fields_count, sensitive_count, violations_count,
                       decision, role, policy_version, target_destination, summary_json,
                       report_markdown, audit_reference, created_at, completed_at
                FROM pipeline_runs
                WHERE execution_id = ?
                LIMIT 1
                """,
                (execution_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["summary"] = json.loads(res["summary_json"])
            except Exception:
                res["summary"] = {}
            return res
        finally:
            await db.close()

    @staticmethod
    async def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
        """List most recent pipeline validation runs."""
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                SELECT id, pipeline_id, execution_id, dataset_name, format, status,
                       risk_level, risk_score, fields_count, sensitive_count, violations_count,
                       decision, role, policy_version, target_destination, summary_json,
                       audit_reference, created_at, completed_at
                FROM pipeline_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["summary"] = json.loads(item["summary_json"])
                except Exception:
                    item["summary"] = {}
                results.append(item)
            return results
        finally:
            await db.close()
