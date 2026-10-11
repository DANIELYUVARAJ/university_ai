"""
University DataShield - Production Observability & Metrics Subsystem
Phase 12: Real-time Operational Telemetry & Monitoring

Collects non-PII, privacy-safe performance and security metrics:
- API Request counts, latencies, and error codes
- Pipeline validation totals (ALLOW, BLOCK, REVIEW, FAILED)
- Publication attempts and gate enforcement blocks
- Policy violations detected
- Authentication & Authorization failures
- Rate limiting 429 events
- Worker queue depths, retry counts, dead letters
- Destination write outcomes
"""

from __future__ import annotations
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List


class MetricsCollector:
    """Thread-safe operational telemetry collector."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_metrics()
            return cls._instance

    def _init_metrics(self):
        self._metrics_lock = threading.Lock()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.request_count = 0
        self.total_duration_ms = 0.0
        self.status_codes: Dict[int, int] = {}
        
        # Pipelines
        self.pipelines_total = 0
        self.pipelines_allowed = 0
        self.pipelines_blocked = 0
        self.pipelines_failed = 0
        self.policy_violations_total = 0

        # Publications
        self.publications_total = 0
        self.publications_allowed = 0
        self.publications_blocked = 0

        # Security & Auth
        self.auth_failures = 0
        self.authz_failures = 0
        self.rate_limit_events = 0

        # Destinations
        self.destination_writes_success = 0
        self.destination_writes_failed = 0

        # Latency samples (last 100 for rolling percentiles)
        self.recent_latencies: List[float] = []

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._metrics_lock:
            self.request_count += 1
            self.total_duration_ms += duration_ms
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
            if status_code == 401:
                self.auth_failures += 1
            elif status_code == 403:
                self.authz_failures += 1
            elif status_code == 429:
                self.rate_limit_events += 1

            self.recent_latencies.append(duration_ms)
            if len(self.recent_latencies) > 200:
                self.recent_latencies.pop(0)

    def record_pipeline(self, decision: str, status: str, violations: int = 0) -> None:
        with self._metrics_lock:
            self.pipelines_total += 1
            self.policy_violations_total += violations
            dec = decision.upper()
            if dec == "ALLOW":
                self.pipelines_allowed += 1
            elif dec == "BLOCK":
                self.pipelines_blocked += 1
            if status.upper() == "FAILED":
                self.pipelines_failed += 1

    def record_publication(self, decision: str, success: bool) -> None:
        with self._metrics_lock:
            self.publications_total += 1
            if decision.upper() == "ALLOW" and success:
                self.publications_allowed += 1
                self.destination_writes_success += 1
            else:
                self.publications_blocked += 1
                if not success and decision.upper() == "ALLOW":
                    self.destination_writes_failed += 1

    def record_destination(self, success: bool) -> None:
        with self._metrics_lock:
            if success:
                self.destination_writes_success += 1
            else:
                self.destination_writes_failed += 1

    def get_summary(self) -> Dict[str, Any]:
        with self._metrics_lock:
            avg_latency = (
                self.total_duration_ms / self.request_count if self.request_count > 0 else 0.0
            )
            p95_latency = 0.0
            if self.recent_latencies:
                sorted_lats = sorted(self.recent_latencies)
                idx = int(0.95 * len(sorted_lats))
                p95_latency = sorted_lats[min(idx, len(sorted_lats) - 1)]

            try:
                from pipeline.worker import pipeline_queue
            except ImportError:
                from backend.pipeline.worker import pipeline_queue
            worker_stats = pipeline_queue.get_stats()

            return {
                "started_at": self.started_at,
                "uptime_seconds": time.time() - datetime.fromisoformat(self.started_at).timestamp(),
                "requests": {
                    "total": self.request_count,
                    "avg_latency_ms": round(avg_latency, 2),
                    "p95_latency_ms": round(p95_latency, 2),
                    "status_breakdown": dict(self.status_codes),
                },
                "pipelines": {
                    "total": self.pipelines_total,
                    "allowed": self.pipelines_allowed,
                    "blocked": self.pipelines_blocked,
                    "failed": self.pipelines_failed,
                    "violations_detected": self.policy_violations_total,
                },
                "publications": {
                    "total": self.publications_total,
                    "allowed": self.publications_allowed,
                    "blocked": self.publications_blocked,
                },
                "security": {
                    "authentication_failures": self.auth_failures,
                    "authorization_denials": self.authz_failures,
                    "rate_limit_events": self.rate_limit_events,
                },
                "destinations": {
                    "writes_success": self.destination_writes_success,
                    "writes_failed": self.destination_writes_failed,
                },
                "worker": {
                    "status": worker_stats.get("status"),
                    "active_workers": worker_stats.get("active_workers"),
                    "queued_jobs": worker_stats.get("queued_jobs"),
                    "running_jobs": worker_stats.get("running_jobs"),
                    "total_jobs": worker_stats.get("total_jobs"),
                },
            }


metrics_collector = MetricsCollector()
