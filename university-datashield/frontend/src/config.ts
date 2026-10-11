/** Base URL for the FastAPI backend. */
export const API_BASE_URL = 'http://localhost:8000'

/** Health endpoint */
export const HEALTH_URL = `${API_BASE_URL}/health`

/** Phase 2: Scan endpoints */
export const SCAN_URL = `${API_BASE_URL}/scan`
export const SCHEMA_URL = `${API_BASE_URL}/scan/schema`

/** Phase 3: Evaluation endpoint */
export const EVALUATE_URL = `${API_BASE_URL}/evaluate`

/** Phase 4: Policy endpoints */
export const POLICIES_URL = `${API_BASE_URL}/policies`
export const POLICIES_VALIDATE_URL = `${API_BASE_URL}/policies/validate`
export const POLICIES_PREVIEW_URL = `${API_BASE_URL}/policies/preview`

/** Phase 5: Access Roles & Publication Gate endpoints */
export const ROLES_URL = `${API_BASE_URL}/roles`
export const PUBLISH_CHECK_URL = `${API_BASE_URL}/publish-check`
export const PUBLISH_URL = `${API_BASE_URL}/publish`

/** Phase 6: Governance, Versioning & Audit endpoints */
export const AUDIT_URL = `${API_BASE_URL}/audit`
export const AUDIT_INTEGRITY_URL = `${API_BASE_URL}/audit/integrity`
export const POLICY_CHANGES_URL = `${API_BASE_URL}/policy-changes`
export const POLICY_PROPOSE_URL = `${API_BASE_URL}/policies/propose`
export const POLICY_APPROVE_URL = `${API_BASE_URL}/policies/approve`
export const POLICY_REJECT_URL = `${API_BASE_URL}/policies/reject`
export const POLICY_VERSIONS_URL = `${API_BASE_URL}/policies/versions`
export const POLICY_DIFF_URL = `${API_BASE_URL}/policies/diff`
export const POLICY_ROLLBACK_URL = `${API_BASE_URL}/policies/rollback`

/** Phase 7: End-to-End Security Validation & Adversarial Testing */
export const SECURITY_VALIDATION_RUN_URL = `${API_BASE_URL}/security-validation/run`
export const SECURITY_VALIDATION_RESULTS_URL = `${API_BASE_URL}/security-validation/results`
export const SECURITY_VALIDATION_METRICS_URL = `${API_BASE_URL}/security-validation/metrics`

/** Phase 8: Final Integration, Executive Summary & Demo Seeding */
export const DASHBOARD_SUMMARY_URL = `${API_BASE_URL}/dashboard/summary`
export const DEMO_RESET_URL = `${API_BASE_URL}/demo/reset`

/** Phase 10: Analytical Pipeline Integration endpoints */
export const PIPELINE_VALIDATE_URL = `${API_BASE_URL}/pipeline/validate`
export const PIPELINE_PREVIEW_URL = `${API_BASE_URL}/pipeline/preview`
export const PIPELINE_PUBLISH_URL = `${API_BASE_URL}/pipeline/publish`
export const PIPELINE_BATCH_URL = `${API_BASE_URL}/pipeline/batch`
export const PIPELINE_RUNS_URL = `${API_BASE_URL}/pipeline/runs`
export const PIPELINE_REPORT_URL = (id: string) => `${API_BASE_URL}/pipeline/${id}/report`

/** Phase 11: Production Security, Scalability, Worker Queue & Readiness */
export const READY_URL = `${API_BASE_URL}/ready`
export const AUTH_TOKEN_URL = `${API_BASE_URL}/auth/token`
export const AUTH_ME_URL = `${API_BASE_URL}/auth/me`
export const PIPELINE_JOBS_URL = `${API_BASE_URL}/pipeline/jobs`
export const PIPELINE_JOBS_SUBMIT_URL = `${API_BASE_URL}/pipeline/jobs/submit`
export const PIPELINE_WORKER_STATS_URL = `${API_BASE_URL}/pipeline/worker/stats`
export const DESTINATION_PUBLISH_URL = `${API_BASE_URL}/pipeline/destination/publish`
export const OPERATIONAL_METRICS_URL = `${API_BASE_URL}/metrics/operational`

/** Phase 13: DataShield AI Assistant */
export const ASSISTANT_STATUS_URL = `${API_BASE_URL}/api/assistant/status`
export const ASSISTANT_ASK_URL = `${API_BASE_URL}/api/assistant/ask`
export const ASSISTANT_EXPLAIN_SCAN_URL = `${API_BASE_URL}/api/assistant/explain-scan`
