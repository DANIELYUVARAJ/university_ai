# backend/pipeline/schemas.py
"""
Pydantic schemas and state machine enums for the Phase 10 Analytical Pipeline Integration.
Enforces zero raw PII retention and strict fail-closed contract definitions.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from policies.schemas import ProtectionAction, FieldValidationInput


class PipelineState(str, Enum):
    """Rigid state machine transitions for analytical pipeline executions."""
    CREATED = "CREATED"
    SCANNING = "SCANNING"
    DETECTED = "DETECTED"
    VALIDATING_POLICY = "VALIDATING_POLICY"
    VALIDATING_ACCESS = "VALIDATING_ACCESS"
    READY = "READY"
    BLOCKED = "BLOCKED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class DatasetFormat(str, Enum):
    CSV = "CSV"
    JSON = "JSON"
    PARQUET = "PARQUET"
    ARROW = "ARROW"
    ORC = "ORC"
    AVRO = "AVRO"
    UNKNOWN = "UNKNOWN"


class FieldIngestionInfo(BaseModel):
    field_name: str
    data_type: str
    sample_value: Optional[str] = None
    pattern_hint: Optional[str] = None


class ExtractedSchema(BaseModel):
    dataset_name: str
    format: DatasetFormat
    row_count: int
    fields: List[FieldIngestionInfo]


class PipelineViolation(BaseModel):
    field: str
    classification: str
    required_action: str
    actual_action: str
    reason: str


class PipelineRecommendation(BaseModel):
    field: str
    recommended_action: str
    reason: str
    preview: Optional[str] = None


class PipelineMaskingPreviewItem(BaseModel):
    field: str
    classification: str
    required_policy: str
    original_sample_type: str
    preview: str


class PipelineValidateRequest(BaseModel):
    dataset_name: str = Field(..., description="Name of the analytical dataset")
    raw_content: Optional[str] = Field(None, description="Raw CSV or JSON dataset string for ingestion")
    format: Optional[DatasetFormat] = Field(None, description="Format (CSV or JSON) if raw_content provided")
    fields: Optional[List[FieldValidationInput]] = Field(None, description="Direct field schema inputs if already extracted")
    role: str = Field("DATA_ENGINEER", description="Role requesting pipeline validation")
    target_destination: str = Field("University Analytics Warehouse", description="Downstream publishing target")
    pipeline_id: Optional[str] = Field(None, description="Explicit or existing pipeline ID")
    execution_id: Optional[str] = Field(None, description="Execution ID for idempotency")
    client_approved: Optional[bool] = Field(None, description="Client assertion flag (untrusted; backend revalidates)")


class PipelineValidateResponse(BaseModel):
    pipeline_id: str
    execution_id: str
    dataset_name: str
    status: PipelineState
    decision: str  # "ALLOW" | "BLOCK"
    detection_status: str  # "PASS" | "REVIEW" | "FAIL"
    policy_status: str  # "PASS" | "FAIL" | "REVIEW"
    authorization_status: str  # "PASS" | "FAIL"
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    risk_score: int
    sensitive_fields: List[str]
    policy_violations: List[PipelineViolation]
    recommended_actions: List[PipelineRecommendation]
    masking_previews: List[PipelineMaskingPreviewItem]
    audit_reference: Optional[str] = None
    policy_version: str
    role: str
    target_destination: str
    message: str
    created_at: str
    completed_at: Optional[str] = None


class PipelinePublishRequest(BaseModel):
    pipeline_id: str
    execution_id: Optional[str] = None
    role: str = Field("DATA_ENGINEER", description="Role executing publication")
    target_destination: str = Field("University Analytics Warehouse", description="Publishing target")
    raw_content: Optional[str] = None
    format: Optional[DatasetFormat] = None
    fields: Optional[List[FieldValidationInput]] = None
    client_approved: Optional[bool] = None


class PipelinePublishResponse(BaseModel):
    pipeline_id: str
    execution_id: str
    status: PipelineState
    decision: str  # "ALLOW" | "BLOCK"
    success: bool
    message: str
    published_at: Optional[str] = None
    target_destination: str
    audit_reference: Optional[str] = None
    reasons: List[str] = []


class BatchValidationItem(BaseModel):
    dataset_name: str
    raw_content: Optional[str] = None
    format: Optional[DatasetFormat] = None
    fields: Optional[List[FieldValidationInput]] = None


class PipelineBatchRequest(BaseModel):
    batch_id: str = Field(..., description="Unique batch run identifier")
    role: str = Field("DATA_ENGINEER", description="Role executing the batch")
    target_destination: str = Field("University Analytics Warehouse", description="Target destination")
    datasets: List[BatchValidationItem]


class BatchSummary(BaseModel):
    batch_id: str
    total_datasets: int
    passed: int
    blocked: int
    failed: int
    review_required: int
    overall_decision: str  # "ALLOW" or "BLOCK"
    fail_closed_triggered: bool


class PipelineBatchResponse(BaseModel):
    batch_id: str
    summary: BatchSummary
    results: List[PipelineValidateResponse]


class PipelineReportResponse(BaseModel):
    pipeline_id: str
    execution_id: str
    dataset_name: str
    status: str
    decision: str
    summary: Dict[str, Any]
    markdown_report: str
