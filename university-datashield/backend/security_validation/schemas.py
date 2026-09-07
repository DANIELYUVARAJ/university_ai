# backend/security_validation/schemas.py
"""
Pydantic schemas and enums for Phase 7 End-to-End Security Validation.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SecuritySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ScenarioCategory(str, Enum):
    PUBLICATION_SAFETY = "PUBLICATION_SAFETY"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    BYPASS_RESISTANCE = "BYPASS_RESISTANCE"
    MASKING_COMPLIANCE = "MASKING_COMPLIANCE"
    FAIL_CLOSED_BEHAVIOR = "FAIL_CLOSED_BEHAVIOR"
    AUDIT_INTEGRITY = "AUDIT_INTEGRITY"
    POLICY_LIFECYCLE = "POLICY_LIFECYCLE"
    FALSE_POSITIVE_RESISTANCE = "FALSE_POSITIVE_RESISTANCE"


class ScenarioStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class SecurityScenarioResult(BaseModel):
    scenario_id: str
    name: str
    category: ScenarioCategory
    description: str
    synthetic_fields: List[Dict[str, Any]]
    attempted_action: str
    expected_decision: str
    actual_decision: str
    status: ScenarioStatus
    severity: SecuritySeverity
    root_cause: Optional[str] = None
    remediation: Optional[str] = None
    audit_event: Optional[str] = None
    notes: Optional[str] = None
    execution_time_ms: float = 0.0


class SecurityMetrics(BaseModel):
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    unsafe_publication_prevention_rate: float
    unauthorized_block_rate: float
    audit_coverage_rate: float
    rollback_recovery_rate: float
    false_block_rate: float
    safe_publication_rate: float
    audit_integrity_detection_rate: float
    detection_precision: float
    detection_recall: float
    detection_f1: float
    detection_accuracy: float


class BaselineComparison(BaseModel):
    metric: str
    baseline_value: str
    datashield_value: str
    interpretation: str


class ErrorAnalysisItem(BaseModel):
    scenario_id: str
    scenario_name: str
    field: str
    expected: str
    actual: str
    failure_reason: str
    severity: SecuritySeverity
    remediation: str


class SecurityValidationReport(BaseModel):
    timestamp: str
    overall_status: str  # "PASS" or "FAIL"
    scenarios_passed: int
    scenarios_total: int
    metrics: SecurityMetrics
    scenarios: List[SecurityScenarioResult]
    baseline_comparison: List[BaselineComparison]
    error_analysis: List[ErrorAnalysisItem]
    privacy_check_passed: bool
