import { useState, useEffect } from 'react'
import { PUBLISH_CHECK_URL, PUBLISH_URL, ROLES_URL } from '../config'
import type {
  PublicationCheckResponse,
  PublishExecutionResponse,
  FieldValidationInput,
  ProtectionAction,
  DemoRole,
  RoleDetail,
} from '../types'
import { ClassificationBadge } from '../components/ScanResultBadges'

// Preset demo scenarios as specified in Section 11 of requirements
const SCENARIO_A_UNSAFE: FieldValidationInput[] = [
  { name: 'email', classification: 'DIRECT_IDENTIFIER', actual_action: 'MASK', sample_value: 'student001@example.edu' },
  { name: 'phone', classification: 'DIRECT_IDENTIFIER', actual_action: 'NONE', sample_value: '+91-9000000001' },
  { name: 'attendance_percentage', classification: 'ACADEMIC_DATA', actual_action: 'NONE', sample_value: '92' },
  { name: 'salary', classification: 'SENSITIVE_ATTRIBUTE', actual_action: 'GENERALIZE', sample_value: '850000' },
]

const SCENARIO_B_SAFE: FieldValidationInput[] = [
  { name: 'email', classification: 'DIRECT_IDENTIFIER', actual_action: 'MASK', sample_value: 'student001@example.edu' },
  { name: 'phone', classification: 'DIRECT_IDENTIFIER', actual_action: 'MASK', sample_value: '+91-9000000001' },
  { name: 'attendance_percentage', classification: 'ACADEMIC_DATA', actual_action: 'NONE', sample_value: '92' },
  { name: 'salary', classification: 'SENSITIVE_ATTRIBUTE', actual_action: 'GENERALIZE', sample_value: '850000' },
]

const PROTECTION_OPTIONS: ProtectionAction[] = ['NONE', 'MASK', 'HASH', 'GENERALIZE', 'SUPPRESS']

export default function PublicationGate() {
  const [selectedRole, setSelectedRole] = useState<DemoRole>('ANALYST')
  const [datasetName, setDatasetName] = useState('University Demo Dataset')
  const [fields, setFields] = useState<FieldValidationInput[]>(SCENARIO_A_UNSAFE)
  const [roles, setRoles] = useState<RoleDetail[]>([])

  const [checking, setChecking] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [checkResult, setCheckResult] = useState<PublicationCheckResponse | null>(null)
  const [publishResult, setPublishResult] = useState<PublishExecutionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load active demo role from localStorage if available
  useEffect(() => {
    const saved = localStorage.getItem('datashield_current_role') as DemoRole | null
    if (saved) setSelectedRole(saved)

    fetch(ROLES_URL)
      .then((res) => res.json())
      .then((data) => setRoles(data))
      .catch(() => {})
  }, [])

  // Action: Evaluate publication safety gate
  const handleValidateBeforePublish = async () => {
    try {
      setChecking(true)
      setError(null)
      setPublishResult(null)

      const res = await fetch(PUBLISH_CHECK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_name: datasetName,
          role: selectedRole,
          fields,
        }),
      })

      if (!res.ok) throw new Error(`Gate check failed: ${res.status}`)
      const json: PublicationCheckResponse = await res.json()
      setCheckResult(json)
    } catch (err: any) {
      setError(err.message || 'Error communicating with publication gate')
    } finally {
      setChecking(false)
    }
  }

  // Action: Execute simulated publication (independently re-checked by backend!)
  const handleSimulatePublish = async () => {
    try {
      setPublishing(true)
      setError(null)

      const res = await fetch(PUBLISH_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_name: datasetName,
          role: selectedRole,
          fields,
          target_destination: 'Institutional Public Analytics Portal',
        }),
      })

      if (!res.ok) throw new Error(`Publish failed: ${res.status}`)
      const json: PublishExecutionResponse = await res.json()
      setPublishResult(json)
    } catch (err: any) {
      setError(err.message || 'Failed to simulate publication')
    } finally {
      setPublishing(false)
    }
  }

  // Load preset scenario
  const applyScenario = (preset: 'A' | 'B' | 'C') => {
    setPublishResult(null)
    setCheckResult(null)
    setError(null)

    if (preset === 'A') {
      setSelectedRole('ANALYST')
      setFields(SCENARIO_A_UNSAFE)
    } else if (preset === 'B') {
      setSelectedRole('ANALYST')
      setFields(SCENARIO_B_SAFE)
    } else if (preset === 'C') {
      setSelectedRole('FACULTY')
      setFields(SCENARIO_B_SAFE)
    }
  }

  // Handle dropdown change on field protection
  const handleFieldActionChange = (fieldName: string, action: ProtectionAction) => {
    const updated = fields.map((f) => (f.name === fieldName ? { ...f, actual_action: action } : f))
    setFields(updated)
    setCheckResult(null)
    setPublishResult(null)
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Publication Safety Gate
            </h1>
            <span className="badge bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 text-xs font-semibold">
              Phase 5 Active
            </span>
            <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-semibold">
              Default Deny Enforced
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Backend enforcement gate preventing analytical publication of unmasked or unauthorized sensitive data.
          </p>
        </div>

        {/* Demo Scenario Quick-Load Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => applyScenario('A')}
            className="btn bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded-lg border border-slate-700"
          >
            Scenario A (Unsafe Phone)
          </button>
          <button
            onClick={() => applyScenario('B')}
            className="btn bg-indigo-950/60 hover:bg-indigo-900/80 text-indigo-300 text-xs px-3 py-1.5 rounded-lg border border-indigo-800"
          >
            Scenario B (Fixed Masked)
          </button>
          <button
            onClick={() => applyScenario('C')}
            className="btn bg-amber-950/60 hover:bg-amber-900/80 text-amber-300 text-xs px-3 py-1.5 rounded-lg border border-amber-800"
          >
            Scenario C (Faculty Role)
          </button>
        </div>
      </div>

      {/* ── Gate Configuration & Context Bar ────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Dataset Name */}
        <div className="card p-4 space-y-1 bg-slate-900/80 border-slate-800">
          <label className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
            Target Dataset
          </label>
          <input
            type="text"
            value={datasetName}
            onChange={(e) => setDatasetName(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 font-medium focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* Selected Role */}
        <div className="card p-4 space-y-1 bg-slate-900/80 border-slate-800">
          <label className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
            Publishing Identity (Role)
          </label>
          <select
            value={selectedRole}
            onChange={(e) => {
              setSelectedRole(e.target.value as DemoRole)
              setCheckResult(null)
              setPublishResult(null)
            }}
            className="w-full bg-slate-950 border border-indigo-500/40 rounded px-2.5 py-1.5 text-xs font-bold text-indigo-300 focus:outline-none focus:border-indigo-400"
          >
            {roles.length > 0
              ? roles.map((r) => (
                  <option key={r.role} value={r.role}>
                    {r.title} ({r.role}) - {r.can_publish ? 'Can Publish' : 'Restricted'}
                  </option>
                ))
              : (
                <>
                  <option value="ANALYST">Data Analyst (ANALYST)</option>
                  <option value="FACULTY">Faculty Member (FACULTY)</option>
                  <option value="DATA_ENGINEER">Data Engineer (DATA_ENGINEER)</option>
                  <option value="PLACEMENT_ADMIN">Placement Admin (PLACEMENT_ADMIN)</option>
                  <option value="SECURITY_ADMIN">Security Admin (SECURITY_ADMIN)</option>
                </>
              )}
          </select>
        </div>

        {/* Primary Action Button */}
        <div className="card p-4 flex items-center justify-between bg-slate-900/80 border-slate-800">
          <div>
            <div className="text-xs font-semibold text-slate-300">Backend Gate Check</div>
            <div className="text-[10px] text-slate-500">Evaluates Role + Policies</div>
          </div>
          <button
            id="validate-before-publish-btn"
            onClick={handleValidateBeforePublish}
            disabled={checking}
            className="btn bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-lg shadow-lg shadow-indigo-900/40 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            <span>{checking ? '🔄 Evaluating...' : 'VALIDATE BEFORE PUBLICATION'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 border-red-500/40 bg-red-500/10 text-red-400 text-xs flex items-center gap-2">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* ── Gate Decision Status Banner (Sections 7, 10, 11) ─────────── */}
      {checkResult && (
        <div
          className={`card p-6 border transition-all ${
            checkResult.decision === 'ALLOW'
              ? 'bg-emerald-950/20 border-emerald-500/40'
              : 'bg-red-950/20 border-red-500/40'
          }`}
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="text-3xl">
                {checkResult.decision === 'ALLOW' ? '🟢' : '🔴'}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <h2
                    className={`text-lg font-bold tracking-tight ${
                      checkResult.decision === 'ALLOW' ? 'text-emerald-400' : 'text-red-400'
                    }`}
                  >
                    {checkResult.decision === 'ALLOW' ? 'SAFE TO PUBLISH' : 'PUBLICATION BLOCKED'}
                  </h2>
                  <span className="badge text-[10px] bg-slate-900 border border-slate-700 font-mono">
                    Status: {checkResult.status}
                  </span>
                </div>

                {checkResult.decision === 'ALLOW' ? (
                  <p className="text-xs text-slate-300">
                    All mandatory protections satisfied. User role <strong>{checkResult.role}</strong> is authorized. No policy violations detected.
                  </p>
                ) : (
                  <div className="text-xs text-red-300/90 space-y-1">
                    <p className="font-semibold">Security Gate Prevented Release:</p>
                    <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                      {checkResult.reasons.map((r, i) => (
                        <li key={i}>
                          {typeof r === 'string' ? r : `${r.field}: ${r.reason}`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Decision Call-To-Action */}
            <div>
              {checkResult.decision === 'ALLOW' ? (
                <button
                  id="simulate-publish-btn"
                  onClick={handleSimulatePublish}
                  disabled={publishing}
                  className="btn bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-5 py-2.5 rounded-lg shadow-lg shadow-emerald-900/40 flex items-center gap-2 transition-all disabled:opacity-50"
                >
                  <span>{publishing ? '🚀 Publishing...' : 'SIMULATE PUBLICATION'}</span>
                </button>
              ) : (
                <button
                  onClick={() => applyScenario('B')}
                  className="btn bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs px-4 py-2 rounded-lg border border-slate-700 transition-all"
                >
                  Quick Fix: Apply Masking
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Simulated Publication Confirmation Toast / Result ──────── */}
      {publishResult && (
        <div className="card p-5 bg-gradient-to-r from-emerald-950/40 to-slate-900 border-emerald-500/50 space-y-2">
          <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
            <span>🚀</span>
            <span>Publication Simulation Complete</span>
          </div>
          <p className="text-xs text-slate-200">{publishResult.message}</p>
          <div className="flex items-center gap-4 text-[10px] text-slate-400 font-mono pt-1">
            <span>Timestamp: {publishResult.simulated_at}</span>
            <span>Role: {publishResult.role}</span>
            <span>Status: Verified by Backend Security Gate</span>
          </div>
        </div>
      )}

      {/* ── Dataset Field Protections Inspector Table ──────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-white">Dataset Field Protections</h3>
            <p className="text-xs text-slate-400">
              Review and interactively adjust actual field protections prior to publication.
            </p>
          </div>
          <span className="badge bg-slate-800 text-slate-400 text-xs">
            {fields.length} Fields Evaluated
          </span>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4 font-semibold">Field</th>
                <th className="py-3 px-3 font-semibold">Classification</th>
                <th className="py-3 px-3 font-semibold">Actual Protection Action</th>
                <th className="py-3 px-3 font-semibold">Gate Inspection Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/30">
              {fields.map((f) => {
                // Find corresponding gate detail if evaluated
                const detail = checkResult?.field_details?.find((d) => d.field === f.name)

                return (
                  <tr key={f.name} className="hover:bg-slate-800/40 transition-colors">
                    {/* Field */}
                    <td className="py-3 px-4 font-mono font-medium text-slate-200">
                      <div>{f.name}</div>
                      {f.sample_value && (
                        <div className="text-[10px] text-slate-500 font-sans">
                          Sample: <span className="font-mono text-slate-400">{f.sample_value}</span>
                        </div>
                      )}
                    </td>

                    {/* Classification */}
                    <td className="py-3 px-3">
                      {f.classification ? (
                        <ClassificationBadge cls={f.classification as any} />
                      ) : (
                        <span className="text-slate-500">Auto-Detect</span>
                      )}
                    </td>

                    {/* Actual Action dropdown */}
                    <td className="py-3 px-3">
                      <select
                        value={f.actual_action}
                        onChange={(e) => handleFieldActionChange(f.name, e.target.value as ProtectionAction)}
                        className={`text-xs font-mono font-semibold rounded px-2.5 py-1.5 border transition-colors ${
                          f.actual_action === 'NONE'
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

                    {/* Gate Inspection Status */}
                    <td className="py-3 px-3">
                      {detail ? (
                        detail.passed ? (
                          <span className="badge bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">
                            🟢 Compliant ({detail.required_action})
                          </span>
                        ) : (
                          <span className="badge bg-red-500/15 text-red-400 border border-red-500/30 text-[10px] font-bold">
                            🔴 Required {detail.required_action}
                          </span>
                        )
                      ) : (
                        <span className="badge bg-slate-800 text-slate-500 text-[10px]">
                          Pending Validation
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
