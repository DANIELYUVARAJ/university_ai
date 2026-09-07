"""
University DataShield – Test Suite
Phase 3: Validation Dataset, Baseline Detector, and Evaluation Engine Tests
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import sys
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from baseline.baseline_detector import BaselineDetector
from baseline.keywords import BASELINE_KEYWORDS
from evaluation.metrics import calculate_binary_metrics
from evaluation.evaluator import EvaluationService, load_validation_dataset, load_ground_truth


# ---------------------------------------------------------------------------
# 1. Dataset Tests
# ---------------------------------------------------------------------------

class TestValidationDataset:
    def test_validation_dataset_loads(self):
        dataset = load_validation_dataset()
        assert isinstance(dataset, list)
        assert 40 <= len(dataset) <= 50

    def test_ground_truth_count_matches_dataset(self):
        dataset = load_validation_dataset()
        ground_truth = load_ground_truth()
        assert len(dataset) == len(ground_truth)

    def test_no_empty_field_names(self):
        dataset = load_validation_dataset()
        for item in dataset:
            assert "field_name" in item
            assert isinstance(item["field_name"], str)
            assert len(item["field_name"].strip()) > 0

    def test_every_field_has_ground_truth_label(self):
        dataset = load_validation_dataset()
        for item in dataset:
            assert "expected_sensitive" in item
            assert isinstance(item["expected_sensitive"], bool)
            assert "expected_classification" in item
            assert len(item["expected_classification"].strip()) > 0

    def test_ground_truth_contains_synthetic_metadata_only(self):
        dataset = load_validation_dataset()
        for item in dataset:
            # Verify sample pattern does not contain real personal data
            pattern = item.get("sample_pattern", "")
            assert "real" not in pattern.lower()
            if "@" in pattern:
                assert "example.edu" in pattern or "example.com" in pattern


# ---------------------------------------------------------------------------
# 2. Baseline Detector Tests
# ---------------------------------------------------------------------------

class TestBaselineDetector:
    @pytest.fixture
    def baseline(self):
        return BaselineDetector()

    def test_baseline_detects_obvious_email(self, baseline):
        res = baseline.predict("student_email")
        assert res["is_sensitive"] is True
        assert res["matched_keyword"] == "email"

    def test_baseline_detects_phone(self, baseline):
        res = baseline.predict("guardian_phone_number")
        assert res["is_sensitive"] is True
        assert res["matched_keyword"] == "phone"

    def test_baseline_detects_student_id(self, baseline):
        res = baseline.predict("student_id")
        assert res["is_sensitive"] is True

    def test_baseline_detects_salary(self, baseline):
        res = baseline.predict("annual_salary")
        assert res["is_sensitive"] is True
        assert res["matched_keyword"] == "salary"

    def test_baseline_demonstrates_keyword_false_positive(self, baseline):
        # email_template_id has keyword 'email' but is non-sensitive
        res_email_tpl = baseline.predict("email_template_id")
        assert res_email_tpl["is_sensitive"] is True

        # phone_model has keyword 'phone' but is non-sensitive
        res_phone_mod = baseline.predict("phone_model")
        assert res_phone_mod["is_sensitive"] is True

        # salary_range_code has keyword 'salary' but is non-sensitive
        res_salary_rng = baseline.predict("salary_range_code")
        assert res_salary_rng["is_sensitive"] is True

    def test_baseline_ignores_clean_non_sensitive_fields(self, baseline):
        assert baseline.predict("classroom_capacity")["is_sensitive"] is False
        assert baseline.predict("semester_count")["is_sensitive"] is False
        assert baseline.predict("course_duration")["is_sensitive"] is False


# ---------------------------------------------------------------------------
# 3. Evaluation Metrics Calculation Tests
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:
    def test_confusion_matrix_counts_are_correct(self):
        y_true = [True, True, False, False]
        y_pred = [True, False, True, False]
        metrics = calculate_binary_metrics(y_true, y_pred)
        assert metrics["true_positives"] == 1
        assert metrics["false_negatives"] == 1
        assert metrics["false_positives"] == 1
        assert metrics["true_negatives"] == 1

    def test_precision_calculation(self):
        # 2 TP, 1 FP -> Precision = 2 / 3 = 0.6667
        y_true = [True, True, False]
        y_pred = [True, True, True]
        metrics = calculate_binary_metrics(y_true, y_pred)
        assert metrics["precision"] == round(2 / 3, 4)

    def test_recall_calculation(self):
        # 1 TP, 1 FN -> Recall = 1 / 2 = 0.5
        y_true = [True, True]
        y_pred = [True, False]
        metrics = calculate_binary_metrics(y_true, y_pred)
        assert metrics["recall"] == 0.5

    def test_f1_calculation(self):
        y_true = [True, True, False, False]
        y_pred = [True, True, False, False]
        metrics = calculate_binary_metrics(y_true, y_pred)
        assert metrics["f1"] == 1.0

    def test_accuracy_calculation(self):
        y_true = [True, False, True, False]
        y_pred = [True, False, False, False]
        # 3 correct out of 4 -> 0.75
        metrics = calculate_binary_metrics(y_true, y_pred)
        assert metrics["accuracy"] == 0.75

    def test_edge_case_empty_predictions(self):
        metrics = calculate_binary_metrics([], [])
        assert metrics["precision"] == 0.0
        assert metrics["recall"] == 0.0
        assert metrics["f1"] == 0.0
        assert metrics["accuracy"] == 0.0


# ---------------------------------------------------------------------------
# 4. End-to-End Evaluation Service & Comparison Tests
# ---------------------------------------------------------------------------

class TestEvaluationService:
    @pytest.fixture
    def eval_service(self):
        return EvaluationService()

    def test_baseline_and_datashield_can_be_compared(self, eval_service):
        results = eval_service.run_evaluation()
        assert "baseline" in results
        assert "datashield" in results
        assert "field_comparisons" in results
        assert "error_analysis" in results
        assert results["total_fields"] >= 40

    def test_datashield_achieves_higher_precision_than_baseline(self, eval_service):
        results = eval_service.run_evaluation()
        ds_precision = results["datashield"]["precision"]
        base_precision = results["baseline"]["precision"]
        # DataShield uses multi-signal checks to eliminate false positives
        assert ds_precision > base_precision

    def test_datashield_has_fewer_false_positives(self, eval_service):
        results = eval_service.run_evaluation()
        ds_fp = results["datashield"]["false_positives"]
        base_fp = results["baseline"]["false_positives"]
        assert ds_fp < base_fp

    def test_error_analysis_identifies_baseline_traps(self, eval_service):
        results = eval_service.run_evaluation()
        error_fields = [e["field"] for e in results["error_analysis"]]
        # Baseline false positives should be in error analysis
        assert "email_template_id" in error_fields
        assert "phone_model" in error_fields


# ---------------------------------------------------------------------------
# 5. API Endpoint Tests (/evaluate)
# ---------------------------------------------------------------------------

class TestEvaluateAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_post_evaluate_endpoint(self, client):
        resp = client.post("/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert "baseline" in data
        assert "datashield" in data
        assert "precision" in data["datashield"]
        assert "recall" in data["datashield"]
        assert "f1" in data["datashield"]
        assert "accuracy" in data["datashield"]
        assert "false_positives" in data["datashield"]
        assert "false_negatives" in data["datashield"]

    def test_get_evaluate_endpoint(self, client):
        resp = client.get("/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_fields"] >= 40
