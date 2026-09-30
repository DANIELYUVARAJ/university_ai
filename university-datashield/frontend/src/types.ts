/** Shape of the /health API response */
export interface HealthResponse {
  status: string
  service: string
  version: string
  phase: number
  database: {
    ok: boolean
    path?: string
    event_count?: number
    error?: string
  }
  data_mode: string
}

export type BackendStatus = 'checking' | 'online' | 'offline'

// ── Phase 2: Scan API types ──────────────────────────────────────────────────

export type Classification =
  | 'DIRECT_IDENTIFIER'
  | 'QUASI_IDENTIFIER'
  | 'SENSITIVE_ATTRIBUTE'
  | 'ACADEMIC_DATA'
  | 'PLACEMENT_DATA'
  | 'NON_SENSITIVE'

export type ConfidenceBand = 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'

export interface FieldInput {
  name: string
  data_type: string
  sample_pattern?: string
}

export interface ScanRequest {
  dataset_name: string
  fields: FieldInput[]
}

export interface SignalBreakdown {
  field_name_match: boolean
  pattern_match: boolean
  data_type_match: boolean
  semantic_match: boolean
  context_match?: boolean
}

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'REVIEW'
export type AmbiguityStatus = 'CLEAR' | 'REVIEW'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type PublicationReadiness = 'READY' | 'NEEDS_PROTECTION' | 'BLOCKED'

export interface DatasetRiskSummary {
  risk_score: number
  risk_level: RiskLevel
  publication_readiness: PublicationReadiness
  direct_identifiers_count: number
  quasi_identifiers_count: number
  sensitive_attributes_count: number
  academic_data_count: number
  placement_data_count: number
  non_sensitive_count: number
  review_fields_count: number
  risk_factors: string[]
  disclaimer: string
}

export interface FieldResult {
  field: string
  data_type: string
  classification: Classification
  confidence: number
  confidence_band: ConfidenceBand
  signals: SignalBreakdown
  reasons: string[]
  normalized_name?: string
  confidence_level?: ConfidenceLevel
  ambiguity_status?: AmbiguityStatus
  contextual_signals?: string[]
  recommendation?: string
}

export interface ScanResponse {
  dataset_name: string
  scan_id: number | null
  fields_scanned: number
  sensitive_count: number
  results: FieldResult[]
  dataset_risk?: DatasetRiskSummary
  publication_readiness?: string
}

// ── Phase 3: Evaluation & Baseline Types ─────────────────────────────────────

export interface BinaryMetrics {
  true_positives: number
  true_negatives: number
  false_positives: number
  false_negatives: number
  precision: number
  recall: number
  f1: number
  accuracy: number
}

export interface FieldComparison {
  field: string
  data_type: string
  sample_pattern?: string
  ground_truth_sensitive: boolean
  ground_truth_classification: string
  baseline_prediction: boolean
  baseline_classification: string
  baseline_error: boolean
  baseline_error_type: string
  datashield_prediction: boolean
  datashield_classification: Classification
  datashield_confidence: number
  datashield_confidence_band: ConfidenceBand
  datashield_signals: SignalBreakdown
  datashield_error: boolean
  datashield_error_type: string
  explanation: string
  reasons: string[]
}

export interface ErrorAnalysisItem {
  field: string
  ground_truth: string
  ground_truth_classification: string
  baseline_prediction: string
  baseline_error_type: string
  datashield_prediction: string
  datashield_classification: string
  datashield_error_type: string
  explanation: string
}

export interface EvaluationResponse {
  total_fields: number
  ground_truth_sensitive_count: number
  ground_truth_nonsensitive_count: number
  baseline: BinaryMetrics
  datashield: BinaryMetrics
  field_comparisons: FieldComparison[]
  error_analysis: ErrorAnalysisItem[]
}

// ── Phase 4: Policy Engine Types ─────────────────────────────────────────────

export type ProtectionAction = 'NONE' | 'MASK' | 'HASH' | 'GENERALIZE' | 'SUPPRESS'
export type ValidationStatus = 'PASS' | 'FAIL' | 'REVIEW'

export interface PolicyRule {
  policy_id: string
  policy_version: string
  target: string
  is_field_override: boolean
  required_action: ProtectionAction
  description?: string
  enabled: boolean
}

export interface PoliciesResponse {
  policy_version: string
  classification_defaults: Record<string, ProtectionAction>
  field_overrides: Record<string, ProtectionAction>
  rules: PolicyRule[]
}

export interface FieldValidationInput {
  name: string
  classification?: string
  actual_action: ProtectionAction
  sample_value?: string
}

export interface FieldValidationResult {
  field: string
  classification: string
  required_action: ProtectionAction
  actual_action: ProtectionAction
  status: ValidationStatus
  reason: string
  is_field_override: boolean
  masked_preview?: string
}

export interface PolicyValidationSummary {
  total_evaluated: number
  protected_count: number
  unprotected_count: number
  violations: number
  review_required: number
  overall_compliance: number
}

export interface PolicyValidationResponse {
  policy_version: string
  overall_status: ValidationStatus
  summary: PolicyValidationSummary
  field_results: FieldValidationResult[]
}

export interface MaskingPreviewResponse {
  field_name: string
  action: ProtectionAction
  original_present: boolean
  masked_value: string
  is_synthetic: boolean
}

// ── Phase 5: Role-Based Access & Publication Gate Types ──────────────────────

export type DemoRole = 'DATA_ENGINEER' | 'ANALYST' | 'FACULTY' | 'PLACEMENT_ADMIN' | 'SECURITY_ADMIN'
export type PublicationDecision = 'ALLOW' | 'BLOCK'
export type PublicationStatus = 'SAFE_TO_PUBLISH' | 'PUBLICATION_BLOCKED' | 'UNAUTHORIZED'

export interface RoleDetail {
  role: DemoRole
  title: string
  description: string
  badge_color: string
  can_publish: boolean
  permissions: {
    VIEW_SCHEMA: boolean
    VIEW_MASKED_DATA: boolean
    VIEW_RAW_SENSITIVE_DATA: boolean | string
    VALIDATE: boolean
    PUBLISH: boolean
    MANAGE_POLICIES: boolean
  }
}

export interface FieldPublicationDetail {
  field: string
  classification: string
  required_action: ProtectionAction
  actual_action: ProtectionAction
  status: string
  passed: boolean
  reason: string
}

export interface PublicationCheckResponse {
  decision: PublicationDecision
  authorized: boolean
  policy_compliant: boolean
  status: PublicationStatus
  dataset_name: string
  role: string
  policy_version: string
  reasons: (string | { field?: string; reason: string })[]
  field_details?: FieldPublicationDetail[]
}

export interface PublishExecutionResponse {
  success: boolean
  decision: PublicationDecision
  status: PublicationStatus
  message: string
  dataset_name: string
  role: string
  reasons: (string | { field?: string; reason: string })[]
  simulated_at: string
  is_simulation: boolean
}

// ── Phase 6: Governance, Audit, Versioning & Rollback Types ──────────────────

export type AuditAction =
  | 'SCAN'
  | 'POLICY_VALIDATION'
  | 'PUBLICATION_CHECK'
  | 'PUBLICATION'
  | 'ACCESS_DENIAL'
  | 'POLICY_CHANGE_PROPOSED'
  | 'POLICY_APPROVED'
  | 'POLICY_REJECTED'
  | 'POLICY_ROLLBACK'

export interface AuditEventRecord {
  id: number
  timestamp: string
  actor_role: string
  actor_id: string
  action: AuditAction
  dataset?: string
  field_name?: string
  result: string
  reason?: string
  policy_version?: string
  change_id?: string
  metadata_json?: Record<string, any>
  previous_hash: string
  event_hash: string
}

export interface AuditIntegrityResponse {
  status: 'VALID' | 'COMPROMISED'
  events_checked: number
  head_hash?: string
  details: string
}

export type PolicyChangeStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'ROLLED_BACK'

export interface ProposedChangeDetail {
  target: string
  is_field_override: boolean
  current_action: ProtectionAction
  proposed_action: ProtectionAction
  description: string
}

export interface PolicyChangeRecord {
  id: string
  requested_at: string
  requested_by_role: string
  requested_by_actor: string
  reason: string
  current_version: string
  proposed_version: string
  proposed_change: ProposedChangeDetail
  status: PolicyChangeStatus
  reviewed_by_role?: string
  reviewed_by_actor?: string
  reviewed_at?: string
  review_reason?: string
}

export interface PolicySnapshot {
  classification_defaults: Record<string, ProtectionAction>
  field_overrides: Record<string, ProtectionAction>
}

export interface PolicyVersionRecord {
  id: number
  version: string
  created_at: string
  created_by: string
  status: 'ACTIVE' | 'SUPERSEDED' | 'ROLLED_BACK'
  parent_version?: string
  change_id?: string
  description: string
  policy_snapshot: PolicySnapshot
  active: boolean
}

export interface PolicyDiffItem {
  target: string
  is_field_override: boolean
  from_action?: ProtectionAction
  to_action?: ProtectionAction
  changed: boolean
}

export interface PolicyDiffResponse {
  from_version: string
  to_version: string
  changes_count: number
  diffs: PolicyDiffItem[]
}

export interface RollbackResponse {
  success: boolean
  resulting_active_version: string
  target_version: string
  previous_version: string
  revalidation_summary: Record<string, any>
  revalidation_status: string
  message: string
}

// ── Phase 7: End-to-End Security Validation & Adversarial Testing Types ───────

export type SecuritySeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

export type ScenarioCategory =
  | 'PUBLICATION_SAFETY'
  | 'RBAC'
  | 'BYPASS_RESISTANCE'
  | 'POLICY_INTEGRITY'
  | 'AUDIT_INTEGRITY'
  | 'EDGE_CASE'

export type ScenarioStatus = 'PASS' | 'FAIL'

export interface SecurityScenarioResult {
  scenario_id: string
  name: string
  category: ScenarioCategory
  description: string
  test_field?: string
  expected_result: string
  actual_result: string
  status: ScenarioStatus
  severity: SecuritySeverity
  audit_event?: string
  notes: string
  root_cause?: string
  remediation?: string
}

export interface SecurityMetrics {
  total_scenarios: number
  passed: number
  failed: number
  unsafe_publication_prevention_rate: number
  unauthorized_block_rate: number
  audit_coverage: number
  rollback_recovery_rate: number
  false_block_rate: number
  safe_publication_rate: number
  audit_integrity_detection_rate: number
  detection_precision: number
  detection_recall: number
  detection_f1: number
  detection_accuracy: number
  detection_false_positives: number
  detection_false_negatives: number
}

export interface BaselineComparison {
  metric: string
  baseline_value: string
  datashield_value: string
  advantage: string
}

export interface ErrorAnalysisItem {
  scenario: string
  field: string
  expected_result: string
  actual_result: string
  failure_reason: string
  severity: SecuritySeverity
  remediation: string
}

export interface SecurityValidationReport {
  generated_at: string
  total_scenarios: number
  passed: number
  failed: number
  metrics: SecurityMetrics
  scenarios: SecurityScenarioResult[]
  baseline_comparisons: BaselineComparison[]
  error_analysis: ErrorAnalysisItem[]
}

// ── Phase 8: Final Integration, Executive Summary & Demo Seeding Types ──────

export interface SystemHealthIndicators {
  backend_connected: boolean
  database_connected: boolean
  policy_engine_active: boolean
  publication_gate_active: boolean
  audit_integrity_valid: boolean
  synthetic_data_mode: boolean
}

export interface ExecutiveMetrics {
  sensitive_fields_detected: number
  protected_fields: number
  blocked_publications: number
  safe_publications: number
  security_scenarios_passed: number
  security_scenarios_total: number
  audit_events_count: number
  audit_integrity_status: string
  active_policy_version: string
  unsafe_publication_prevention_rate: number
  unauthorized_block_rate: number
  audit_coverage: number
  rollback_recovery_rate: number
  false_block_rate: number
  detection_f1: number
  detection_precision: number
  detection_recall: number
}

export interface DashboardSummaryResponse {
  status: string
  system_health: SystemHealthIndicators
  metrics: ExecutiveMetrics
  phase: number
  environment: string
}

export interface DemoResetResponse {
  status: string
  active_version: string
  audit_events_count: number
  integrity_status: string
  message: string
}

// ── Phase 10: Analytical Pipeline Integration Types ─────────────────────────

export type PipelineState =
  | 'CREATED'
  | 'SCANNING'
  | 'DETECTED'
  | 'VALIDATING_POLICY'
  | 'VALIDATING_ACCESS'
  | 'READY'
  | 'BLOCKED'
  | 'PUBLISHED'
  | 'FAILED'

export interface PipelineViolation {
  field: string
  classification: string
  required_action: string
  actual_action: string
  reason: string
}

export interface PipelineRecommendation {
  field: string
  recommended_action: string
  reason: string
  preview?: string
}

export interface PipelineMaskingPreviewItem {
  field: string
  classification: string
  required_policy: string
  original_sample_type: string
  preview: string
}

export interface PipelineValidateResponse {
  pipeline_id: string
  execution_id: string
  dataset_name: string
  status: PipelineState
  decision: 'ALLOW' | 'BLOCK'
  detection_status: string
  policy_status: string
  authorization_status: string
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  risk_score: number
  sensitive_fields: string[]
  policy_violations: PipelineViolation[]
  recommended_actions: PipelineRecommendation[]
  masking_previews: PipelineMaskingPreviewItem[]
  audit_reference?: string
  policy_version: string
  role: string
  target_destination: string
  message: string
  created_at: string
  completed_at?: string
}

export interface PipelineRunRecord {
  id: number
  pipeline_id: string
  execution_id: string
  dataset_name: string
  format: string
  status: PipelineState
  risk_level: string
  risk_score: number
  fields_count: number
  sensitive_count: number
  violations_count: number
  decision: 'ALLOW' | 'BLOCK'
  role: string
  policy_version: string
  target_destination: string
  summary: Record<string, any>
  report_markdown?: string
  audit_reference?: string
  created_at: string
  completed_at?: string
}

export interface BatchSummary {
  batch_id: string
  total_datasets: number
  passed: number
  blocked: number
  failed: number
  review_required: number
  overall_decision: 'ALLOW' | 'BLOCK'
  fail_closed_triggered: boolean
}

export interface PipelineBatchResponse {
  batch_id: string
  summary: BatchSummary
  results: PipelineValidateResponse[]
}

export interface PipelineReportResponse {
  pipeline_id: string
  execution_id: string
  dataset_name: string
  status: string
  decision: string
  summary: Record<string, any>
  markdown_report: string
}

