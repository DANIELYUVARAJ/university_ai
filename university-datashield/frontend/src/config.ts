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
