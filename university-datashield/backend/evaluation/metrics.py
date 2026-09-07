# backend/evaluation/metrics.py
"""
Metrics calculation module for sensitive field discovery evaluation.
Calculates TP, TN, FP, FN, Precision, Recall, F1, and Accuracy.
"""

from typing import Dict, Any, List

def calculate_binary_metrics(y_true: List[bool], y_pred: List[bool]) -> Dict[str, Any]:
    """
    Compute binary classification metrics for sensitive vs non-sensitive detection.
    True = Sensitive, False = Non-Sensitive.
    """
    tp = 0
    tn = 0
    fp = 0
    fn = 0

    for actual, pred in zip(y_true, y_pred):
        if actual and pred:
            tp += 1
        elif not actual and not pred:
            tn += 1
        elif not actual and pred:
            fp += 1
        elif actual and not pred:
            fn += 1

    total = tp + tn + fp + fn
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    accuracy = ((tp + tn) / total) if total > 0 else 0.0

    return {
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }
