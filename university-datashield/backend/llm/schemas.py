"""
University DataShield - LLM Assistant Schemas
Phase 13: Local AI Assistant for College Demonstration and Viva
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class AssistantStatusResponse(BaseModel):
    """Health and status of the local LLM provider."""
    model_config = {"protected_namespaces": ()}

    enabled: bool = True
    available: bool = False
    provider: str = "ollama"
    base_url: str
    configured_model: str
    model_found: bool = False
    installed_models: List[str] = Field(default_factory=list)
    setup_instructions: str
    advisory_notice: str = (
        "Advisory Only: AI suggestions cannot approve publication, override policy gates, "
        "or alter server-side security decisions."
    )


class QuestionRequest(BaseModel):
    """User prompt asking about sensitive data, FERPA, or masking policies."""
    question: str
    context: Optional[Union[str, Dict[str, Any]]] = None


class QuestionResponse(BaseModel):
    """Explanation and guidance from the assistant."""
    model_config = {"protected_namespaces": ()}

    question: str
    answer: str
    explanation: Optional[str] = None
    provider: str  # "ollama" or "deterministic_rule_engine"
    model: str
    is_advisory: bool = True
    policy_engine_validated: bool = True
    execution_time_ms: float = 0.0
    advisory_warning: str = (
        "AI recommendations are purely advisory and require authoritative verification by the DataShield Policy Engine."
    )
    warning: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.explanation:
            self.explanation = self.answer
        if not self.warning:
            self.warning = self.advisory_warning


class SyntheticFieldFinding(BaseModel):
    """Synthetic field metadata for assistant explanation (no real personal data)."""
    field_name: str
    detected_type: Optional[str] = "string"
    inferred_classification: Optional[str] = None
    sample_synthetic_values: Optional[List[str]] = Field(default_factory=list)


class ExplainScanRequest(BaseModel):
    """Request to explain findings from a completed synthetic schema scan."""
    dataset_name: str = "synthetic_academic_cohort"
    fields: List[SyntheticFieldFinding]


class FieldExplanation(BaseModel):
    """Explanation and recommended policy for a single synthetic field."""
    field_name: str
    classification: str
    sensitivity_rationale: str
    suggested_policy: str  # MASK, HASH, GENERALIZE, SUPPRESS
    policy_rationale: str
    deterministic_validation_status: str  # COMPLIANT, VIOLATION, REVIEW_REQUIRED
    policy_engine_rule: str


class ExplainScanResponse(BaseModel):
    """Structured response explaining scan findings with deterministic verification."""
    model_config = {"protected_namespaces": ()}

    dataset_name: str
    provider: str
    model: str
    overall_summary: str
    blocking_findings_explanation: Optional[str] = None
    field_explanations: List[FieldExplanation]
    publication_gate_verdict: str  # ALLOW, BLOCK, REVIEW
    authoritative_notice: str = (
        "Server-Side Security Enforced: All AI policy recommendations have been cross-checked "
        "against the active DataShield Policy Engine v1.0. Gate decisions remain authoritative."
    )
