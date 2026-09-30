# backend/pipeline/__init__.py
"""
University DataShield – Pipeline Subsystem (Phase 10).
Provides analytical pipeline ingestion, validation, fail-closed publication gates,
idempotency, batch processing, and audit trail integration.
"""

from .schemas import (
    PipelineState,
    DatasetFormat,
    FieldIngestionInfo,
    ExtractedSchema,
    PipelineViolation,
    PipelineRecommendation,
    PipelineMaskingPreviewItem,
    PipelineValidateRequest,
    PipelineValidateResponse,
    PipelinePublishRequest,
    PipelinePublishResponse,
    BatchValidationItem,
    PipelineBatchRequest,
    BatchSummary,
    PipelineBatchResponse,
    PipelineReportResponse,
)
from .ingestion import DatasetIngestionService
from .repository import PipelineRepository
from .pipeline_service import PipelineService, generate_pipeline_id, generate_execution_id

__all__ = [
    "PipelineState",
    "DatasetFormat",
    "FieldIngestionInfo",
    "ExtractedSchema",
    "PipelineViolation",
    "PipelineRecommendation",
    "PipelineMaskingPreviewItem",
    "PipelineValidateRequest",
    "PipelineValidateResponse",
    "PipelinePublishRequest",
    "PipelinePublishResponse",
    "BatchValidationItem",
    "PipelineBatchRequest",
    "BatchSummary",
    "PipelineBatchResponse",
    "PipelineReportResponse",
    "DatasetIngestionService",
    "PipelineRepository",
    "PipelineService",
    "generate_pipeline_id",
    "generate_execution_id",
]
