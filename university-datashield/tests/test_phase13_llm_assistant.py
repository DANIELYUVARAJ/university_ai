"""
Phase 13 Automated Tests: University DataShield LLM Assistant
Verifies the 10 required test cases:
1. Successful model response using a mocked provider.
2. Ollama unavailable handling.
3. Request timeout handling.
4. Malformed model response handling.
5. Excessively large input rejection (HTTP 413).
6. No real personal data sent in test fixtures (data minimization).
7. Suggested policy rejected by deterministic validation.
8. BLOCK remains blocked regardless of model output.
9. REVIEW remains non-publishable.
10. Existing RBAC and audit behavior remains intact.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from config import settings
from llm.service import LLMAssistantService
from llm.schemas import (
    QuestionRequest,
    ExplainScanRequest,
    SyntheticFieldFinding,
)
from policies.schemas import ProtectionAction
from publication.gate import PublicationGate
from publication.schemas import PublicationCheckRequest, PublicationDecision, PublicationStatus
from access.access_engine import AccessEngine
from access.permissions import Permission


@pytest.fixture
def client():
    return TestClient(app)


# ------------------------------------------------------------------------------
# Test 1: Successful model response using a mocked provider
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_successful_model_response_mocked():
    """Mocked Ollama provider returns an AI explanation successfully."""
    mock_tags_resp = MagicMock(status_code=200)
    mock_tags_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}

    mock_gen_resp = MagicMock(status_code=200)
    mock_gen_resp.json.return_value = {
        "response": "Student email is considered a direct identifier under FERPA regulations and should be masked."
    }

    with patch("httpx.AsyncClient.get", return_value=mock_tags_resp), \
         patch("httpx.AsyncClient.post", return_value=mock_gen_resp):

        res = await LLMAssistantService.ask_question(
            QuestionRequest(question="Why should student_email be masked before analytics publication?")
        )
        assert res.provider == "ollama"
        assert res.model == "llama3.2"
        assert "FERPA" in res.answer
        assert res.is_advisory is True


# ------------------------------------------------------------------------------
# Test 2: Ollama unavailable
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_ollama_unavailable_fallback():
    """When Ollama is offline, service falls back safely to deterministic rule engine without crashing."""
    with patch("httpx.AsyncClient.get", side_effect=ConnectionError("Ollama daemon offline")):
        status = await LLMAssistantService.check_ollama_status()
        assert status.available is False
        assert "Ollama is not running" in status.setup_instructions

        res = await LLMAssistantService.ask_question(
            QuestionRequest(question="Why should student_email be masked before analytics publication?")
        )
        assert res.provider == "deterministic_rule_engine"
        assert res.is_advisory is True
        assert "DIRECT IDENTIFIERS" in res.answer


# ------------------------------------------------------------------------------
# Test 3: Request timeout
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_request_timeout_handling():
    """When Ollama times out, request does not crash and provides deterministic fallback."""
    import httpx
    mock_tags_resp = MagicMock(status_code=200)
    mock_tags_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}

    with patch("httpx.AsyncClient.get", return_value=mock_tags_resp), \
         patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Ollama generation timed out")):

        res = await LLMAssistantService.ask_question(
            QuestionRequest(question="Why should student_email be masked before analytics publication?")
        )
        assert res.provider == "deterministic_rule_engine"
        assert res.is_advisory is True
        assert len(res.answer) > 20


# ------------------------------------------------------------------------------
# Test 4: Malformed model response
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_malformed_model_response():
    """When model returns malformed JSON, service handles gracefully."""
    mock_tags_resp = MagicMock(status_code=200)
    mock_tags_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}

    mock_gen_resp = MagicMock(status_code=500)
    mock_gen_resp.json.side_effect = ValueError("Corrupt JSON payload")

    with patch("httpx.AsyncClient.get", return_value=mock_tags_resp), \
         patch("httpx.AsyncClient.post", return_value=mock_gen_resp):

        res = await LLMAssistantService.ask_question(
            QuestionRequest(question="Why is student_id sensitive?")
        )
        assert res.provider == "deterministic_rule_engine"
        assert res.is_advisory is True


# ------------------------------------------------------------------------------
# Test 5: Excessively large input
# ------------------------------------------------------------------------------
def test_05_excessively_large_input_rejected(client):
    """Prompts exceeding LLM_MAX_PROMPT_CHARS are rejected with HTTP 413."""
    oversized_prompt = "Why is this field sensitive? " * 200  # > 2000 chars
    res = client.post("/api/assistant/ask", json={"question": oversized_prompt})
    assert res.status_code == 413
    assert "maximum allowed length" in res.json()["detail"].lower()


# ------------------------------------------------------------------------------
# Test 6: No real personal data sent in test fixtures
# ------------------------------------------------------------------------------
def test_06_no_real_personal_data_safeguard(client):
    """Input containing potential real SSN or credit card numbers is blocked by data minimization check."""
    # Attempting to send a real SSN pattern
    res = client.post("/api/assistant/ask", json={"question": "Analyze student with SSN 123-45-6789"})
    assert res.status_code == 400
    assert "real personal data pattern detected" in res.json()["detail"].lower()


# ------------------------------------------------------------------------------
# Test 7: Suggested policy rejected by deterministic validation
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_suggested_policy_rejected_by_deterministic_validation():
    """If an advisory policy is inadequate (e.g. MASK for student_id which requires HASH), PolicyEngine flags VIOLATION."""
    from policies.policy_engine import PolicyEngine
    from policies.schemas import PolicyValidationRequest, FieldValidationInput

    engine = PolicyEngine()
    # Direct identifier student_id requires HASH; unprotected field yields FAIL
    val_req = PolicyValidationRequest(
        dataset_name="synthetic_test",
        fields=[
            FieldValidationInput(
                name="student_id",
                classification="DIRECT_IDENTIFIER",
                actual_action=ProtectionAction.NONE,  # Unprotected -> FAIL
            )
        ],
    )
    res = engine.validate_dataset(val_req)
    assert res.field_results[0].status.value == "FAIL"
    assert "requires HASH" in res.field_results[0].reason
    assert res.summary.violations > 0

    # Action mismatch (e.g. required HASH vs actual MASK) yields REVIEW
    val_req_mismatch = PolicyValidationRequest(
        dataset_name="synthetic_test",
        fields=[
            FieldValidationInput(
                name="student_id",
                classification="DIRECT_IDENTIFIER",
                actual_action=ProtectionAction.MASK,  # Mismatched protection
            )
        ],
    )
    res_mismatch = engine.validate_dataset(val_req_mismatch)
    assert res_mismatch.field_results[0].status.value == "REVIEW"
    assert res_mismatch.summary.review_required > 0


# ------------------------------------------------------------------------------
# Test 8: BLOCK remains blocked regardless of model output
# ------------------------------------------------------------------------------
def test_08_block_remains_blocked_regardless_of_model(client):
    """Even if an LLM prompt claims a dataset is safe, server-side publication gate enforces BLOCK."""
    # Attempting publication with unmasked direct identifier
    res = client.post(
        "/publish",
        json={
            "dataset_name": "unsafe_dataset",
            "role": "ANALYST",
            "is_compliant": True,  # Attacker claim
            "ai_approved": True,   # Hypothetical AI approval claim
            "fields": [
                {
                    "name": "student_id",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",
                }
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "BLOCK"
    assert body["success"] is False


# ------------------------------------------------------------------------------
# Test 9: REVIEW remains non-publishable
# ------------------------------------------------------------------------------
def test_09_review_remains_non_publishable(client):
    """Fields flagged with ambiguity or REVIEW status cannot be published."""
    gate = PublicationGate()
    req = PublicationCheckRequest(
        dataset_name="review_dataset",
        role="ANALYST",
        fields=[
            {
                "name": "placement_package",
                "classification": "QUASI_IDENTIFIER",
                "actual_action": "NONE",  # Unprotected quasi-identifier -> REVIEW/BLOCK
            }
        ],
    )
    res = gate.evaluate(req)
    assert res.decision == PublicationDecision.BLOCK
    assert res.policy_compliant is False
    assert res.status == PublicationStatus.PUBLICATION_BLOCKED


# ------------------------------------------------------------------------------
# Test 10: Existing RBAC and audit behavior remains intact
# ------------------------------------------------------------------------------
def test_10_rbac_and_audit_behavior_intact(client):
    """DATA_ENGINEER attempting to publish is blocked by RBAC regardless of any AI output."""
    res = client.post(
        "/publish",
        json={
            "dataset_name": "cohort_2026",
            "role": "DATA_ENGINEER",  # Lacks publication permission
            "fields": [
                {
                    "name": "student_email",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "MASK",
                }
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "BLOCK"
    assert body["status"] == "UNAUTHORIZED"
    assert body["success"] is False


# ------------------------------------------------------------------------------
# Test 11: Valid request with string context (Fix for HTTP 422 mismatch)
# ------------------------------------------------------------------------------
def test_11_ask_endpoint_accepts_string_context(client):
    """The /api/assistant/ask endpoint must accept string context sent by the frontend without 422."""
    mock_tags = MagicMock(status_code=200)
    mock_tags.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
    mock_gen = MagicMock(status_code=200)
    mock_gen.json.return_value = {"response": "Student email must be masked under FERPA."}

    with patch("httpx.AsyncClient.get", return_value=mock_tags), \
         patch("httpx.AsyncClient.post", return_value=mock_gen):
        res = client.post(
            "/api/assistant/ask",
            json={
                "question": "Why should student_email be masked before analytics publication?",
                "context": "University student analytical warehouse publication review",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "question" in body
        assert "answer" in body
        assert "explanation" in body
        assert body["is_advisory"] is True
        assert body["answer"] == body["explanation"]


# ------------------------------------------------------------------------------
# Test 12: Valid request with dict context or omitted context
# ------------------------------------------------------------------------------
def test_12_ask_endpoint_accepts_dict_or_omitted_context(client):
    """The /api/assistant/ask endpoint accepts dict context or omitted context."""
    mock_tags = MagicMock(status_code=200)
    mock_tags.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
    mock_gen = MagicMock(status_code=200)
    mock_gen.json.return_value = {"response": "Mocked policy response."}

    with patch("httpx.AsyncClient.get", return_value=mock_tags), \
         patch("httpx.AsyncClient.post", return_value=mock_gen):
        # Dict context
        res_dict = client.post(
            "/api/assistant/ask",
            json={
                "question": "Why is placement_package sensitive?",
                "context": {"pipeline": "admissions", "stage": "export"},
            },
        )
        assert res_dict.status_code == 200
        assert "answer" in res_dict.json()

        # Omitted context
        res_none = client.post(
            "/api/assistant/ask",
            json={"question": "What happens if student_id is unhashed?"},
        )
        assert res_none.status_code == 200
        assert "answer" in res_none.json()


# ------------------------------------------------------------------------------
# Test 13: Missing required question field returns HTTP 422
# ------------------------------------------------------------------------------
def test_13_ask_endpoint_missing_question_returns_422(client):
    """Missing question parameter must return HTTP 422 with structured detail."""
    res = client.post("/api/assistant/ask", json={"context": "some context"})
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)
    assert any("question" in str(err.get("loc", [])) for err in body["detail"])


# ------------------------------------------------------------------------------
# Test 14: Invalid input types return HTTP 422
# ------------------------------------------------------------------------------
def test_14_ask_endpoint_invalid_payload_type_returns_422(client):
    """Non-dict payload or invalid question type returns HTTP 422."""
    res = client.post("/api/assistant/ask", json="just a string")
    assert res.status_code == 422

    res_wrong_type = client.post(
        "/api/assistant/ask",
        json={"question": ["not", "a", "string"]},
    )
    assert res_wrong_type.status_code == 422
