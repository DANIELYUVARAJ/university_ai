# backend/evaluation/evaluator.py
"""
Evaluation engine for benchmarking the DataShield detection engine against the baseline detector.
Uses ground truth labels from the synthetic validation dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from baseline.baseline_detector import BaselineDetector
from detection.detector import scan_field
from detection.schemas import FieldInput
from .metrics import calculate_binary_metrics


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"
VALIDATION_DATASET_PATH = DATA_DIR / "validation_dataset.json"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"


def load_validation_dataset(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the synthetic validation dataset."""
    target_path = path or VALIDATION_DATASET_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Validation dataset not found at {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ground_truth(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the ground truth labels."""
    target_path = path or GROUND_TRUTH_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Ground truth file not found at {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)


class EvaluationService:
    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path or VALIDATION_DATASET_PATH
        self.baseline = BaselineDetector()

    def run_evaluation(self, custom_dataset: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Runs both Baseline and DataShield detectors over the evaluation dataset.
        Computes precision, recall, F1, accuracy, and full error analysis.
        """
        dataset = custom_dataset or load_validation_dataset(self.dataset_path)

        y_true: List[bool] = []
        y_baseline: List[bool] = []
        y_datashield: List[bool] = []

        field_comparisons: List[Dict[str, Any]] = []
        error_analysis: List[Dict[str, Any]] = []

        for item in dataset:
            field_name = item["field_name"]
            data_type = item.get("data_type", "string")
            sample_pattern = item.get("sample_pattern", "")
            gt_sensitive = bool(item["expected_sensitive"])
            gt_classification = item.get("expected_classification", "NON_SENSITIVE")

            # 1. Run baseline
            base_res = self.baseline.predict(field_name)
            base_pred = base_res["is_sensitive"]
            base_class = base_res["classification"]

            # 2. Run DataShield
            field_input = FieldInput(
                name=field_name,
                data_type=data_type,
                sample_pattern=sample_pattern
            )
            ds_res = scan_field(field_input)
            ds_pred = ds_res.classification != "NON_SENSITIVE"
            ds_class = ds_res.classification
            ds_conf = ds_res.confidence

            # Track labels
            y_true.append(gt_sensitive)
            y_baseline.append(base_pred)
            y_datashield.append(ds_pred)

            # Error determination
            base_is_error = base_pred != gt_sensitive
            ds_is_error = ds_pred != gt_sensitive

            def get_error_type(pred: bool, actual: bool) -> str:
                if pred == actual:
                    return "Correct"
                if pred and not actual:
                    return "False Positive"
                return "False Negative"

            base_error_type = get_error_type(base_pred, gt_sensitive)
            ds_error_type = get_error_type(ds_pred, gt_sensitive)

            # Build human explanation
            explanation_parts = []
            if base_is_error:
                if base_error_type == "False Positive":
                    explanation_parts.append(f"Baseline false positive on keyword '{base_res.get('matched_keyword')}'")
                else:
                    explanation_parts.append("Baseline missed field (no keyword match)")
            
            if ds_is_error:
                if ds_error_type == "False Positive":
                    explanation_parts.append(f"DataShield false positive ({ds_class})")
                else:
                    explanation_parts.append(f"DataShield false negative: rules/patterns did not trigger")
            elif not base_is_error and not ds_is_error:
                explanation_parts.append("Both detectors predicted correctly")
            elif not ds_is_error and base_is_error:
                explanation_parts.append("DataShield multi-signal evaluation avoided baseline error")

            explanation = "; ".join(explanation_parts)

            comparison_entry = {
                "field": field_name,
                "data_type": data_type,
                "sample_pattern": sample_pattern,
                "ground_truth_sensitive": gt_sensitive,
                "ground_truth_classification": gt_classification,
                "baseline_prediction": base_pred,
                "baseline_classification": base_class,
                "baseline_error": base_is_error,
                "baseline_error_type": base_error_type,
                "datashield_prediction": ds_pred,
                "datashield_classification": ds_class,
                "datashield_confidence": ds_conf,
                "datashield_confidence_band": ds_res.confidence_band,
                "datashield_signals": ds_res.signals.model_dump(),
                "datashield_error": ds_is_error,
                "datashield_error_type": ds_error_type,
                "explanation": explanation,
                "reasons": ds_res.reasons
            }
            field_comparisons.append(comparison_entry)

            # Record in error analysis if either made an error
            if base_is_error or ds_is_error:
                error_analysis.append({
                    "field": field_name,
                    "ground_truth": "Sensitive" if gt_sensitive else "Non-sensitive",
                    "ground_truth_classification": gt_classification,
                    "baseline_prediction": "Sensitive" if base_pred else "Non-sensitive",
                    "baseline_error_type": base_error_type,
                    "datashield_prediction": "Sensitive" if ds_pred else "Non-sensitive",
                    "datashield_classification": ds_class,
                    "datashield_error_type": ds_error_type,
                    "explanation": explanation
                })

        baseline_metrics = calculate_binary_metrics(y_true, y_baseline)
        datashield_metrics = calculate_binary_metrics(y_true, y_datashield)

        return {
            "total_fields": len(dataset),
            "ground_truth_sensitive_count": sum(1 for y in y_true if y),
            "ground_truth_nonsensitive_count": sum(1 for y in y_true if not y),
            "baseline": baseline_metrics,
            "datashield": datashield_metrics,
            "field_comparisons": field_comparisons,
            "error_analysis": error_analysis
        }
