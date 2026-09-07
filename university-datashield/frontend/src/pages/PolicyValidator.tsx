import { useState, useEffect } from 'react'
import { POLICIES_URL, POLICIES_VALIDATE_URL, POLICIES_PREVIEW_URL } from '../config'
import type {
  PoliciesResponse,
  PolicyValidationResponse,
  FieldValidationInput,
  FieldValidationResult,
  ProtectionAction,
  ValidationStatus,
  Classification,
} from '../types'
import { ClassificationBadge } from '../components/ScanResultBadges'

// Standard realistic demonstration fields illustrating PASS, FAIL, and REVIEW states
const DEMO_FIELDS_PRESET: FieldValidationInput[] = [
  { name: 'email', classification: 'DIRECT_IDENTIFIER', actual_action: 'MASK', sample_value: 'student001@example.edu' },
  { name: 'phone', classification: 'DIRECT_IDENTIFIER', actual_action: 'NONE', sample_value: '+91-9000000001' },
  { name: 'student_id', classification: 'DIRECT_IDENTIFIER', actual_action: 'HASH', sample_value: 'STU_DEMO_001' },
  { name: 'date_of_birth', classification: 'QUASI_IDENTIFIER', actual_action: 'GENERALIZE', sample_value: '1999-04-17' },
  { name: 'birth_year', classification: 'QUASI_IDENTIFIER', actual_action: 'GENERALIZE', sample_value: '1999' },
  { name: 'salary', classification: 'SENSITIVE_ATTRIBUTE', actual_action: 'MASK', sample_value: '850000' }, // REVIEW state
  { name: 'placement_package', classification: 'SENSITIVE_ATTRIBUTE', actual_action: 'NONE', sample_value: '750000' }, // FAIL state
  { name: 'guardian_contact', classification: 'DIRECT_IDENTIFIER', actual_action: 'MASK', sample_value: '+91-9000000003' },
  { name: 'course_code', classification: 'NON_SENSITIVE', actual_action: 'NONE', sample_value: 'CS401' },
  { name: 'semester', classification: 'NON_SENSITIVE', actual_action: 'NONE', sample_value: '5' },
  { name: 'attendance_percentage', classification: 'ACADEMIC_DATA', actual_action: 'NONE', sample_value: '92' },
  { name: 'candidate_id', classification: 'DIRECT_IDENTIFIER', actual_action: 'NONE', sample_value: 'CAND_DEMO_042' }, // FAIL state
]

const PROTECTION_OPTIONS: ProtectionAction[] = ['NONE', 'MASK', 'HASH', 'GENERALIZE', 'SUPPRESS']

export default function PolicyValidator() {
  const [policies, setPolicies] = useState<PoliciesResponse | null>(null)
  const [validationData, setValidationData] = useState<PolicyValidationResponse | null>(null)
  const [editableFields, setEditableFields] = useState<FieldValidationInput[]>(DEMO_FIELDS_PRESET)
  const [loading, setLoading] = useState(true)
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<'ALL' | ValidationStatus>('ALL')

  // Masking Sandbox state
  const [sandboxField, setSandboxField] = useState('student_email')
  const [sandboxAction, setSandboxAction] = useState<ProtectionAction>('MASK')
  const [sandboxInput, setSandboxInput] = useState('student001@example.edu')
  const [sandboxOutput, setSandboxOutput] = useState('')
  const [sandboxLoading, setSandboxLoading] = useState(false)

  // Fetch active policies and initial validation
  const loadPoliciesAndValidate = async () => {
    try {
      setLoading(true)
      setError(null)

      // 1. Fetch active policies
      const polRes = await fetch(POLICIES_URL)
      if (!polRes.ok) throw new Error(`Failed to load policies: ${polRes.status}`)
      const polData: PoliciesResponse = await polRes.json()
      setPolicies(polData)

      // 2. Run initial validation on preset
      await runValidation(editableFields)
    } catch (err: any) {
      setError(err.message || 'Error connecting to policy engine')
    } finally {
      setLoading(false)
    }
  }

  const runValidation = async (fieldsToValidate: FieldValidationInput[]) => {
    try {
      setValidating(true)
      const res = await fetch(POLICIES_VALIDATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_name: 'university_evaluation_schema',
          fields: fieldsToValidate,
        }),
      })
      if (!res.ok) throw new Error(`Validation failed with status ${res.status}`)
      const json: PolicyValidationResponse = await res.json()
      setValidationData(json)
    } catch (err: any) {
      setError(err.message || 'Validation request failed')
    } finally {
      setValidating(false)
    }
  }

  // Handle dropdown change on a field's actual protection
  const handleActionChange = (fieldName: string, newAction: ProtectionAction) => {
    const updated = editableFields.map((f) =>
      f.name === fieldName ? { ...f, actual_action: newAction } : f
    )
    setEditableFields(updated)
    runValidation(updated)
  }

  // Run masking preview demonstration
  const handlePreviewMasking = async () => {
    try {
      setSandboxLoading(true)
      const res = await fetch(POLICIES_PREVIEW_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field_name: sandboxField,
          action: sandboxAction,
          value: sandboxInput,
        }),
      })
      if (!res.ok) throw new Error(`Preview failed: ${res.status}`)
      const json = await res.json()
      setSandboxOutput(json.masked_value)
    } catch (err: any) {
      setSandboxOutput(`[Error: ${err.message}]`)
    } finally {
      setSandboxLoading(false)
    }
  }

  useEffect(() => {
    loadPoliciesAndValidate()
    handlePreviewMasking()
  }, [])

  // Action change in sandbox triggers preview auto-update
  useEffect(() => {
    handlePreviewMasking()
  }, [sandboxAction, sandboxInput, sandboxField])

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="inline-block animate-spin text-3xl">🛡️</div>
          <div className="text-lg font-medium text-slate-200">Loading Masking Policy Engine...</div>
          <p className="text-sm text-slate-500">Retrieving active policy rules and evaluating field compliance.</p>
        </div>
      </div>
    )
  }

  if (error || !validationData) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center">
        <div className="card p-8 max-w-md text-center space-y-4 border-red-500/30 bg-red-500/5">
          <div className="text-3xl">⚠️</div>
          <h2 className="text-lg font-bold text-red-400">Policy Engine Offline</h2>
          <p className="text-sm text-slate-400">{error}</p>
          <button onClick={loadPoliciesAndValidate} className="btn btn-primary px-4 py-2 text-sm mx-auto">
            Retry Connection
          </button>
        </div>
      </div>
    )
  }

  const { summary, field_results, policy_version } = validationData

  const filteredResults = field_results.filter((item) => {
    if (filterStatus === 'ALL') return true
    return item.status === filterStatus
  })

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Masking Policy Validator
            </h1>
            <span className="badge bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 text-xs font-semibold">
              Policy Version: {policy_version}
            </span>
            <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-semibold">
              Phase 4 Active
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Compare detected sensitive fields against mandatory protection policies and validate actual protection states.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => runValidation(editableFields)}
            disabled={validating}
            className="btn bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-4 py-2 rounded-lg flex items-center gap-2 shadow-lg shadow-indigo-900/30 transition-all disabled:opacity-50"
          >
            <span>{validating ? '🔄 Validating...' : '⚡ Re-evaluate Policies'}</span>
          </button>
        </div>
      </div>

      {/* ── Summary KPI Cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Fields Evaluated */}
        <div className="card p-5 space-y-2 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Fields Evaluated</span>
          <div className="text-2xl font-bold text-slate-200">{summary.total_evaluated}</div>
          <div className="text-[11px] text-slate-500">Schema Attributes</div>
        </div>

        {/* Protected */}
        <div className="card p-5 space-y-2 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Protected Fields</span>
          <div className="text-2xl font-bold text-indigo-400">{summary.protected_count}</div>
          <div className="text-[11px] text-slate-500">Mask, Hash or Generalized</div>
        </div>

        {/* Violations (FAIL) */}
        <div className="card p-5 space-y-2 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Violations</span>
            <span className="w-2 h-2 rounded-full bg-red-400 animate-ping" />
          </div>
          <div className="text-2xl font-bold text-red-400">{summary.violations}</div>
          <div className="text-[11px] text-red-400/80">🔴 Action Required</div>
        </div>

        {/* Review Required */}
        <div className="card p-5 space-y-2 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Review Required</span>
          <div className="text-2xl font-bold text-amber-400">{summary.review_required}</div>
          <div className="text-[11px] text-amber-400/80">🟡 Protection Mismatch</div>
        </div>

        {/* Overall Compliance */}
        <div className="card p-5 space-y-2 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Overall Compliance</span>
          <div className="text-2xl font-bold text-emerald-400">{summary.overall_compliance}%</div>
          <div className="text-[11px] text-emerald-400/80">
            {summary.overall_compliance >= 90 ? '🟢 Audit Compliant' : '⚠️ Non-Compliant Release'}
          </div>
        </div>
      </div>

      {/* ── Main Layout: Policy Validation Table + Masking Preview ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 cols): Policy Validation Table */}
        <div className="lg:col-span-8 card p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>Field Policy Validation</span>
                <span className="badge text-[10px] bg-slate-800 text-slate-400 border border-slate-700">
                  {filteredResults.length} Fields
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Live verification of required vs applied masking protections.
              </p>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 text-xs bg-slate-900/90 p-1 rounded-lg border border-slate-800">
              <button
                onClick={() => setFilterStatus('ALL')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  filterStatus === 'ALL' ? 'bg-slate-800 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All ({field_results.length})
              </button>
              <button
                onClick={() => setFilterStatus('FAIL')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  filterStatus === 'FAIL'
                    ? 'bg-red-500/20 text-red-300 font-semibold border border-red-500/30'
                    : 'text-slate-400 hover:text-red-300'
                }`}
              >
                🔴 Fail ({summary.violations})
              </button>
              <button
                onClick={() => setFilterStatus('REVIEW')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  filterStatus === 'REVIEW'
                    ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30'
                    : 'text-slate-400 hover:text-amber-300'
                }`}
              >
                🟡 Review ({summary.review_required})
              </button>
              <button
                onClick={() => setFilterStatus('PASS')}
                className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                  filterStatus === 'PASS'
                    ? 'bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30'
                    : 'text-slate-400 hover:text-emerald-300'
                }`}
              >
                🟢 Pass ({summary.total_evaluated - summary.violations - summary.review_required})
              </button>
            </div>
          </div>

          {/* Validation Table */}
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-3 font-semibold">Field</th>
                  <th className="py-3 px-3 font-semibold">Classification</th>
                  <th className="py-3 px-3 font-semibold">Required</th>
                  <th className="py-3 px-3 font-semibold">Actual Action (Interactive)</th>
                  <th className="py-3 px-3 font-semibold">Status</th>
                  <th className="py-3 px-3 font-semibold">Policy Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/30">
                {filteredResults.map((row: FieldValidationResult) => {
                  const statusBadge =
                    row.status === 'PASS' ? (
                      <span className="badge bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                        🟢 PASS
                      </span>
                    ) : row.status === 'FAIL' ? (
                      <span className="badge bg-red-500/15 text-red-400 border border-red-500/30 font-bold">
                        🔴 FAIL
                      </span>
                    ) : (
                      <span className="badge bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold">
                        🟡 REVIEW
                      </span>
                    )

                  return (
                    <tr key={row.field} className="hover:bg-slate-800/40 transition-colors">
                      {/* Field */}
                      <td className="py-3 px-3 font-mono font-medium text-slate-200">
                        <div className="flex items-center gap-1.5">
                          <span>{row.field}</span>
                          {row.is_field_override && (
                            <span className="badge bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[9px] px-1 py-0">
                              Override
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Classification */}
                      <td className="py-3 px-3">
                        <ClassificationBadge cls={row.classification as Classification} />
                      </td>

                      {/* Required */}
                      <td className="py-3 px-3">
                        <span className="badge bg-slate-800 text-slate-300 font-mono font-bold text-[10px]">
                          {row.required_action}
                        </span>
                      </td>

                      {/* Actual Action dropdown */}
                      <td className="py-3 px-3">
                        <select
                          value={row.actual_action}
                          onChange={(e) => handleActionChange(row.field, e.target.value as ProtectionAction)}
                          className={`text-xs font-mono font-semibold rounded px-2 py-1 border transition-colors ${
                            row.actual_action === 'NONE'
                              ? 'bg-slate-900 border-slate-700 text-slate-400'
                              : 'bg-slate-900 border-indigo-500/50 text-indigo-300'
                          }`}
                        >
                          {PROTECTION_OPTIONS.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-3">{statusBadge}</td>

                      {/* Reason */}
                      <td className="py-3 px-3 text-slate-400 text-[11px] max-w-xs">
                        <div>{row.reason}</div>
                        {row.masked_preview && (
                          <div className="mt-1 text-[10px] text-slate-500 font-mono">
                            Preview: <span className="text-slate-300">{row.masked_preview}</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column (4 cols): Masking Demonstration Sandbox + Policy Reference */}
        <div className="lg:col-span-4 space-y-6">
          {/* Masking Preview Demonstration Sandbox */}
          <div className="card p-6 space-y-4 border-indigo-900/40 bg-gradient-to-b from-slate-900 via-slate-900/90 to-indigo-950/20">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-base">🧪</span>
                <h3 className="text-sm font-bold text-white">Masking Demonstration</h3>
              </div>
              <span className="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px]">
                Interactive Preview
              </span>
            </div>

            <div className="space-y-3 text-xs">
              {/* Preset Sample Selector */}
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Quick Synthetic Example:</label>
                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    onClick={() => {
                      setSandboxField('email')
                      setSandboxAction('MASK')
                      setSandboxInput('student001@example.edu')
                    }}
                    className="p-1.5 text-left rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 truncate"
                  >
                    📧 Email (Mask)
                  </button>
                  <button
                    onClick={() => {
                      setSandboxField('phone')
                      setSandboxAction('MASK')
                      setSandboxInput('+91-9000000001')
                    }}
                    className="p-1.5 text-left rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 truncate"
                  >
                    📞 Phone (Mask)
                  </button>
                  <button
                    onClick={() => {
                      setSandboxField('student_id')
                      setSandboxAction('HASH')
                      setSandboxInput('STU_DEMO_001')
                    }}
                    className="p-1.5 text-left rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 truncate"
                  >
                    🔑 ID (SHA-256)
                  </button>
                  <button
                    onClick={() => {
                      setSandboxField('salary')
                      setSandboxAction('GENERALIZE')
                      setSandboxInput('850000')
                    }}
                    className="p-1.5 text-left rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 truncate"
                  >
                    💰 Salary (Band)
                  </button>
                </div>
              </div>

              {/* Protection Action Buttons */}
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Protection Action:</label>
                <div className="grid grid-cols-3 gap-1">
                  {PROTECTION_OPTIONS.filter((o) => o !== 'NONE').map((act) => (
                    <button
                      key={act}
                      onClick={() => setSandboxAction(act)}
                      className={`p-1.5 rounded font-mono font-semibold transition-all ${
                        sandboxAction === act
                          ? 'bg-indigo-600 text-white shadow'
                          : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {act}
                    </button>
                  ))}
                </div>
              </div>

              {/* Synthetic Input */}
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Synthetic Input:</label>
                <input
                  type="text"
                  value={sandboxInput}
                  onChange={(e) => setSandboxInput(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200 font-mono text-xs focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Protected Output */}
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Protected Output:</label>
                <div className="w-full bg-slate-950 border border-indigo-500/40 rounded p-2.5 font-mono text-xs text-emerald-400 break-all min-h-[38px] flex items-center">
                  {sandboxLoading ? 'Transforming...' : sandboxOutput || '[NONE]'}
                </div>
              </div>

              {/* Privacy Notice Required by Prompt */}
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] leading-relaxed">
                🔒 <strong>Synthetic Demonstration Value</strong>
                <p className="text-[10px] text-amber-400/80 mt-0.5">
                  Operates purely on synthetic sample data. No real student personal information is used or persisted.
                </p>
              </div>
            </div>
          </div>

          {/* Policy Rules Overview */}
          {policies && (
            <div className="card p-5 space-y-3 border-slate-800 bg-slate-900/60 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <h4 className="font-bold text-slate-200">Active Policy Set ({policies.policy_version})</h4>
                <span className="badge bg-slate-800 text-slate-400 text-[10px]">Configured</span>
              </div>

              <div className="space-y-2">
                <div className="text-slate-400 font-medium">Classification Defaults:</div>
                <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
                  {Object.entries(policies.classification_defaults).map(([cls, act]) => (
                    <div key={cls} className="p-1.5 rounded bg-slate-950/80 flex justify-between">
                      <span className="text-slate-400 truncate">{cls.replace('_', ' ')}:</span>
                      <span className="text-indigo-400 font-bold ml-1">{act}</span>
                    </div>
                  ))}
                </div>

                <div className="text-slate-400 font-medium pt-2">Field Overrides (High Priority):</div>
                <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
                  {Object.entries(policies.field_overrides).slice(0, 6).map(([fld, act]) => (
                    <div key={fld} className="p-1.5 rounded bg-slate-950/80 flex justify-between">
                      <span className="text-purple-300 truncate">{fld}:</span>
                      <span className="text-purple-400 font-bold ml-1">{act}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
