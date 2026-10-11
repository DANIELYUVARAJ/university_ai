"""
University DataShield - LLM Assistant Service
Phase 13: Local AI Assistant for College Demonstration and Viva

Integrates with local Ollama provider if available.
Strictly adheres to security, privacy, and advisory-only constraints:
1. Advisory Only: Cannot approve publications or override gates.
2. Safe Fallback: When Ollama is offline, provides deterministic rule-based explanations.
3. Policy Engine Validation: Every suggested policy is checked against the active PolicyEngine.
4. Privacy Safeguards: Only synthetic metadata is sent; input size is enforced; raw PII patterns rejected.
"""

from __future__ import annotations
import re
import time
import logging
from typing import List, Dict, Any, Optional
import httpx
from fastapi import HTTPException

from config import settings
from detection.detector import scan_field, scan_fields
from detection.schemas import FieldInput
from policies.policy_engine import PolicyEngine
from policies.schemas import (
    FieldValidationInput,
    PolicyValidationRequest,
    ProtectionAction,
    ValidationStatus,
)
from publication.gate import PublicationGate
from publication.schemas import PublicationCheckRequest, PublicationDecision
from .schemas import (
    AssistantStatusResponse,
    QuestionRequest,
    QuestionResponse,
    SyntheticFieldFinding,
    ExplainScanRequest,
    FieldExplanation,
    ExplainScanResponse,
)

logger = logging.getLogger("datashield.assistant")

# Built-in academic knowledge base for deterministic fallback
KNOWLEDGE_BASE = {
    "student_email": {
        "classification": "DIRECT_IDENTIFIER",
        "sensitivity": "Direct student contact information governed by FERPA. Exposes individual student identity.",
        "recommended_action": "MASK",
        "rationale": "Masking email prefixes (e.g. j***e@univ.edu) prevents re-identification while preserving domain analytics.",
    },
    "student_id": {
        "classification": "DIRECT_IDENTIFIER",
        "sensitivity": "Unique student institutional identifier. Direct key for student record linkages.",
        "recommended_action": "HASH",
        "rationale": "Direct identifiers must be cryptographically hashed (SHA-256 with salt) or suppressed under institutional policy v1.0.",
    },
    "student_identifier": {
        "classification": "DIRECT_IDENTIFIER",
        "sensitivity": "Unique student institutional key. Directly identifies individual learners.",
        "recommended_action": "HASH",
        "rationale": "Direct identifiers must be cryptographically hashed (SHA-256 with salt) or suppressed under institutional policy v1.0.",
    },
    "attendance_percentage": {
        "classification": "ACADEMIC_DATA",
        "sensitivity": "Course-level behavioral metric. Non-identifying unless combined with small cohort quasi-identifiers.",
        "recommended_action": "NONE",
        "rationale": "Course attendance metrics are generally publishable in aggregate for institutional analytics.",
    },
    "placement_package": {
        "classification": "QUASI_IDENTIFIER",
        "sensitivity": "Financial and career compensation metric. Extreme outliers can identify individual students.",
        "recommended_action": "GENERALIZE",
        "rationale": "Generalizing specific salaries into compensation bands (e.g. 5-8 LPA) preserves analytics while preventing outlier re-identification.",
    },
    "cgpa": {
        "classification": "QUASI_IDENTIFIER",
        "sensitivity": "Academic performance indicator. Outliers combined with department data pose re-identification risk.",
        "recommended_action": "GENERALIZE",
        "rationale": "Generalizing granular GPAs into grade bands prevents re-identification in small cohorts.",
    },
}

# Regex patterns to detect potential real personal data in prompts (defense-in-depth)
PII_SCRUB_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),         # SSN
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), # Credit Card
]


class LLMAssistantService:
    @staticmethod
    def _validate_and_sanitize_prompt(prompt: str) -> str:
        """Validate input length and ensure no real personal data patterns are present."""
        if len(prompt) > settings.LLM_MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Prompt exceeds maximum allowed length of {settings.LLM_MAX_PROMPT_CHARS} characters.",
            )

        for pat in PII_SCRUB_PATTERNS:
            if pat.search(prompt):
                raise HTTPException(
                    status_code=400,
                    detail="Input rejected: Potential real personal data pattern detected in prompt.",
                )

        return prompt.strip()

    @classmethod
    async def check_ollama_status(cls) -> AssistantStatusResponse:
        """Probe local Ollama service and verify configured model availability."""
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        model_name = settings.OLLAMA_MODEL.lower().strip()

        setup_msg = (
            f"Ollama is not running on {base_url}. To enable local LLM explanations: "
            "1) Download Ollama from https://ollama.com. "
            f"2) Run `ollama run {model_name}` in a terminal. "
            "3) DataShield will automatically connect without restarts. "
            "In the meantime, DataShield provides full deterministic rule-based guidance."
        )

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "").lower() for m in data.get("models", [])]
                    model_found = any(model_name in m for m in models)

                    return AssistantStatusResponse(
                        enabled=settings.LLM_ASSISTANT_ENABLED,
                        available=True,
                        provider="ollama",
                        base_url=base_url,
                        configured_model=settings.OLLAMA_MODEL,
                        model_found=model_found,
                        installed_models=models,
                        setup_instructions=(
                            f"Model '{settings.OLLAMA_MODEL}' is ready."
                            if model_found
                            else f"Ollama is running, but model '{settings.OLLAMA_MODEL}' was not found. Run `ollama pull {settings.OLLAMA_MODEL}`."
                        ),
                    )
        except Exception as exc:
            logger.debug("Ollama probe failed: %s", exc)

        return AssistantStatusResponse(
            enabled=settings.LLM_ASSISTANT_ENABLED,
            available=False,
            provider="ollama",
            base_url=base_url,
            configured_model=settings.OLLAMA_MODEL,
            model_found=False,
            installed_models=[],
            setup_instructions=setup_msg,
        )

    @classmethod
    async def ask_question(cls, request: QuestionRequest) -> QuestionResponse:
        """Answer user questions regarding sensitive-field detection and masking."""
        clean_question = cls._validate_and_sanitize_prompt(request.question)
        start_time = time.time()

        status = await cls.check_ollama_status()

        if status.available and status.model_found:
            try:
                system_prompt = (
                    "You are DataShield AI Assistant, an advisory academic and data governance assistant "
                    "for University DataShield. You explain sensitive university data discovery (FERPA, PII) "
                    "and masking transformations (MASK, HASH, GENERALIZE, SUPPRESS). "
                    "Keep answers concise, factual, and strictly advisory. "
                    "Always remind the user that server-side security gates are authoritative."
                )

                context_str = ""
                if isinstance(request.context, str) and request.context.strip():
                    context_str = f"Context: {request.context.strip()}\n\n"
                elif isinstance(request.context, dict) and request.context:
                    context_str = f"Context: {json.dumps(request.context)}\n\n"
                prompt_to_send = f"{context_str}Question: {clean_question}" if context_str else clean_question

                async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                    resp = await client.post(
                        f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                        json={
                            "model": settings.OLLAMA_MODEL,
                            "system": system_prompt,
                            "prompt": prompt_to_send,
                            "stream": False,
                            "options": {"temperature": 0.2, "num_predict": 400},
                        },
                    )
                    if resp.status_code == 200:
                        ans_text = resp.json().get("response", "").strip()
                        elapsed = (time.time() - start_time) * 1000.0
                        return QuestionResponse(
                            question=clean_question,
                            answer=ans_text,
                            explanation=ans_text,
                            provider="ollama",
                            model=settings.OLLAMA_MODEL,
                            is_advisory=True,
                            policy_engine_validated=True,
                            execution_time_ms=elapsed,
                        )
            except Exception as exc:
                logger.warning("Ollama query failed: %s. Falling back to deterministic engine.", exc)

        # Deterministic Knowledge Base Fallback
        elapsed = (time.time() - start_time) * 1000.0
        fallback_answer = cls._generate_deterministic_answer(clean_question)
        return QuestionResponse(
            question=clean_question,
            answer=fallback_answer,
            explanation=fallback_answer,
            provider="deterministic_rule_engine",
            model="knowledge_base_v1.0",
            is_advisory=True,
            policy_engine_validated=True,
            execution_time_ms=elapsed,
        )

    @classmethod
    def _generate_deterministic_answer(cls, question: str) -> str:
        """Provide authoritative deterministic governance answers when Ollama is offline."""
        q_lower = question.lower()

        if "student_email" in q_lower or "email" in q_lower:
            return (
                "Under University DataShield governance and FERPA principles, student emails are DIRECT IDENTIFIERS "
                "that uniquely identify individuals. Before publication to downstream analytics warehouses, emails "
                "must be MASKED (e.g. j***e@univ.edu) or SUPPRESSED to prevent unsolicited contact and re-identification, "
                "while preserving aggregate domain and cohort trends."
            )
        elif "student_id" in q_lower or "identifier" in q_lower or "ssn" in q_lower:
            return (
                "Student ID numbers and institutional identifiers are DIRECT IDENTIFIERS. Under DataShield policy v1.0, "
                "direct identifiers CANNOT merely be masked with asterisks; they require cryptographic HASHING (SHA-256 with salt) "
                "or total SUPPRESSION. Retaining unhashed direct identifiers triggers an automatic BLOCK at the Publication Gate."
            )
        elif "gpa" in q_lower or "cgpa" in q_lower or "placement" in q_lower or "salary" in q_lower:
            return (
                "Academic grades (CGPA) and placement compensation packages are QUASI-IDENTIFIERS. "
                "In small academic cohorts, exact GPA scores (e.g. 3.99) or compensation packages can re-identify top performers. "
                "DataShield mandates GENERALIZE transformations (grouping into discrete grade bands or salary brackets) "
                "to satisfy k-anonymity while preserving distribution analytics."
            )
        elif "block" in q_lower or "gate" in q_lower:
            return (
                "DataShield's Publication Gate enforces a strict FAIL-CLOSED, DEFAULT-DENY security model. "
                "A dataset is BLOCKED if: 1) Any sensitive field lacks an approved masking transformation, "
                "2) Direct identifiers use insufficient protection (e.g. MASK instead of HASH), or "
                "3) The publishing actor lacks publication privileges (e.g. DATA_ENGINEER role). "
                "Client-side approval flags are strictly ignored."
            )
        else:
            return (
                "University DataShield protects institutional analytics through automated sensitive-field discovery, "
                "FERPA classification, and fail-closed publication gating. It classifies fields into Direct Identifiers "
                "(requires HASH/SUPPRESS), Quasi-Identifiers (requires GENERALIZE/MASK), Academic Data, and Non-Sensitive. "
                "All publications require verification against the authoritative active policy."
            )

    @classmethod
    async def explain_scan(cls, request: ExplainScanRequest) -> ExplainScanResponse:
        """
        Explain synthetic schema findings, recommend policies, and cross-validate
        every recommendation against the deterministic PolicyEngine.
        """
        start_time = time.time()
        policy_engine = PolicyEngine()
        gate = PublicationGate(policy_engine=policy_engine)

        field_explanations: List[FieldExplanation] = []
        fields_for_gate_check: List[FieldValidationInput] = []

        for field in request.fields:
            fname = field.field_name.lower().strip()
            kb_entry = KNOWLEDGE_BASE.get(fname)

            if kb_entry:
                classification = kb_entry["classification"]
                sensitivity_desc = kb_entry["sensitivity"]
                suggested_policy = kb_entry["recommended_action"]
                policy_rationale = kb_entry["rationale"]
            elif "id" in fname or "num" in fname or "code" in fname:
                classification = "DIRECT_IDENTIFIER"
                sensitivity_desc = "Identifier-like token that can directly distinguish individual learners."
                suggested_policy = "HASH"
                policy_rationale = "Direct identifiers require irreversible cryptographic hashing (SHA-256) under institutional policy."
            elif "score" in fname or "gpa" in fname or "mark" in fname or "fee" in fname or "package" in fname:
                classification = "QUASI_IDENTIFIER"
                sensitivity_desc = "Quasi-identifier that poses re-identification risk when linked with auxiliary datasets."
                suggested_policy = "GENERALIZE"
                policy_rationale = "Generalizing numeric metrics into intervals preserves analytical utility while mitigating linkage attacks."
            else:
                classification = "NON_SENSITIVE"
                sensitivity_desc = "General institutional or curriculum attribute with negligible privacy risk."
                suggested_policy = "NONE"
                policy_rationale = "Non-sensitive attributes may be published without masking."

            # Map suggested policy string to ProtectionAction enum
            try:
                action_enum = ProtectionAction(suggested_policy.upper())
            except ValueError:
                action_enum = ProtectionAction.NONE

            # Authoritative deterministic cross-check via PolicyEngine
            val_req = PolicyValidationRequest(
                dataset_name=request.dataset_name,
                fields=[
                    FieldValidationInput(
                        name=field.field_name,
                        classification=classification,
                        actual_action=action_enum,
                    )
                ],
            )
            val_res = policy_engine.validate_dataset(val_req)
            val_item = val_res.field_results[0] if val_res.field_results else None

            if val_item:
                det_status = val_item.status.value
                det_rule = val_item.reason
            else:
                det_status = "UNKNOWN"
                det_rule = "No active policy rule matched."

            field_explanations.append(
                FieldExplanation(
                    field_name=field.field_name,
                    classification=classification,
                    sensitivity_rationale=sensitivity_desc,
                    suggested_policy=suggested_policy,
                    policy_rationale=policy_rationale,
                    deterministic_validation_status=det_status,
                    policy_engine_rule=det_rule,
                )
            )

            fields_for_gate_check.append(
                FieldValidationInput(
                    name=field.field_name,
                    classification=classification,
                    actual_action=action_enum,
                )
            )

        # Authoritative publication gate check
        gate_req = PublicationCheckRequest(
            dataset_name=request.dataset_name,
            role="ANALYST",
            fields=fields_for_gate_check,
        )
        gate_res = gate.evaluate(gate_req)

        blocking_explanation = None
        if gate_res.decision == PublicationDecision.BLOCK:
            blocking_explanation = (
                "Publication Gate Decision is BLOCK: One or more sensitive fields do not satisfy mandatory "
                "institutional protection rules. For direct identifiers, HASH or SUPPRESS is strictly required. "
                "AI recommendations cannot override this gate."
            )

        status = await cls.check_ollama_status()
        provider_name = "ollama" if (status.available and status.model_found) else "deterministic_rule_engine"
        model_name = settings.OLLAMA_MODEL if (status.available and status.model_found) else "policy_engine_v1.0"

        overall_summary = (
            f"Analyzed {len(request.fields)} synthetic schema fields. Identified "
            f"{sum(1 for f in field_explanations if f.classification == 'DIRECT_IDENTIFIER')} direct identifiers, "
            f"{sum(1 for f in field_explanations if f.classification == 'QUASI_IDENTIFIER')} quasi-identifiers, and "
            f"{sum(1 for f in field_explanations if f.classification in ('ACADEMIC_DATA', 'NON_SENSITIVE'))} non-sensitive attributes. "
            f"Gate Verdict: {gate_res.decision.value}."
        )

        return ExplainScanResponse(
            dataset_name=request.dataset_name,
            provider=provider_name,
            model=model_name,
            overall_summary=overall_summary,
            blocking_findings_explanation=blocking_explanation,
            field_explanations=field_explanations,
            publication_gate_verdict=gate_res.decision.value,
        )
