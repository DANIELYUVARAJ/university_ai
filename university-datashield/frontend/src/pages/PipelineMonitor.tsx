import { useState, useEffect } from 'react'
import {
  PIPELINE_VALIDATE_URL,
  PIPELINE_PREVIEW_URL,
  PIPELINE_PUBLISH_URL,
  PIPELINE_BATCH_URL,
  PIPELINE_RUNS_URL,
  PIPELINE_REPORT_URL,
  READY_URL,
  PIPELINE_WORKER_STATS_URL,
} from '../config'
import type {
  PipelineState,
  PipelineValidateResponse,
  PipelineRunRecord,
  PipelineBatchResponse,
  PipelineReportResponse,
  DemoRole,
} from '../types'

const PRESET_UNPROTECTED_CSV = `student_id,full_name,student_email,contact_phone,cgpa,department
STU_2026_001,Aarav Sharma,aarav.s@university.edu,+91-9876543210,3.88,Computer Science
STU_2026_002,Priya Patel,priya.p@university.edu,+91-9876543211,3.92,Data Science
STU_2026_003,Rohan Verma,rohan.v@university.edu,+91-9876543212,3.75,Information Technology`

const PRESET_PROTECTED_JSON = JSON.stringify([
  {
    "student_id": "c89b27fb9b6a",
    "full_name": "A**** S*****",
    "student_email": "a******@university.edu",
    "contact_phone": "********10",
    "cgpa": 3.88,
    "department": "Computer Science"
  },
  {
    "student_id": "9f3e483f9b18",
    "full_name": "P**** P****",
    "student_email": "p******@university.edu",
    "contact_phone": "********11",
    "cgpa": 3.92,
    "department": "Data Science"
  }
], null, 2)

const PRESET_CORRUPT_CSV = `student_id,name,
STU_001,"Broken line without closed quotes,`

export default function PipelineMonitor() {
  const [activeTab, setActiveTab] = useState<'single' | 'batch' | 'history'>('single')
  const [role, setRole] = useState<DemoRole>('DATA_ENGINEER')
  const [datasetName, setDatasetName] = useState('student_admissions_analytics.csv')
  const [targetDestination, setTargetDestination] = useState('University Central Data Warehouse')
  const [rawContent, setRawContent] = useState(PRESET_UNPROTECTED_CSV)
  const [clientApproved, setClientApproved] = useState(false)

  // Running states
  const [loading, setLoading] = useState(false)
  const [validateResult, setValidateResult] = useState<PipelineValidateResponse | null>(null)
  const [batchResult, setBatchResult] = useState<PipelineBatchResponse | null>(null)
  const [runsList, setRunsList] = useState<PipelineRunRecord[]>([])
  const [reportModal, setReportModal] = useState<PipelineReportResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [readyStatus, setReadyStatus] = useState<any>(null)
  const [workerStats, setWorkerStats] = useState<any>(null)

  // Fetch runs on mount
  useEffect(() => {
    fetchRuns()
    fetchSystemStatus()
  }, [])

  const fetchRuns = async () => {
    try {
      const res = await fetch(PIPELINE_RUNS_URL)
      if (res.ok) {
        const data = await res.json()
        setRunsList(data)
      }
    } catch {
      // Offline or network error handled gracefully
    }
  }

  const fetchSystemStatus = async () => {
    try {
      const [readyRes, workerRes] = await Promise.all([
        fetch(READY_URL),
        fetch(PIPELINE_WORKER_STATS_URL),
      ])
      if (readyRes.ok) setReadyStatus(await readyRes.json())
      if (workerRes.ok) setWorkerStats(await workerRes.json())
    } catch {
      // Offline or network error handled gracefully
    }
  }

  // Single validation
  const handleValidate = async () => {
    setLoading(true)
    setErrorMsg(null)
    setValidateResult(null)
    try {
      const payload = {
        dataset_name: datasetName,
        raw_content: rawContent,
        role: role,
        target_destination: targetDestination,
        client_approved: clientApproved,
      }
      const res = await fetch(PIPELINE_VALIDATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Validation failed')
      }
      setValidateResult(data)
      fetchRuns()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error executing pipeline validation')
    } finally {
      setLoading(false)
    }
  }

  // Preview transformations without recording a run
  const handlePreview = async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const payload = {
        dataset_name: datasetName,
        raw_content: rawContent,
        role: role,
        target_destination: targetDestination,
      }
      const res = await fetch(PIPELINE_PREVIEW_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (data.masking_previews) {
        // Trigger validate to show full card with previews
        handleValidate()
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error executing preview')
    } finally {
      setLoading(false)
    }
  }

  // Attempt publication
  const handlePublish = async () => {
    if (!validateResult) return
    setLoading(true)
    setErrorMsg(null)
    try {
      const payload = {
        pipeline_id: validateResult.pipeline_id,
        execution_id: validateResult.execution_id,
        role: role,
        target_destination: targetDestination,
        raw_content: rawContent,
        client_approved: clientApproved,
      }
      const res = await fetch(PIPELINE_PUBLISH_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (data.success) {
        setValidateResult((prev) => prev ? { ...prev, status: 'PUBLISHED', decision: 'ALLOW' } : null)
      } else {
        setErrorMsg(data.message || 'Publication was BLOCKED by DataShield Security Gate.')
      }
      fetchRuns()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error executing publication')
    } finally {
      setLoading(false)
    }
  }

  // Batch validation
  const handleRunBatch = async () => {
    setLoading(true)
    setErrorMsg(null)
    setBatchResult(null)
    try {
      const payload = {
        batch_id: `BATCH-${Date.now().toString().slice(-6)}`,
        role: role,
        target_destination: targetDestination,
        datasets: [
          {
            dataset_name: 'synthetic_admissions.csv',
            raw_content: PRESET_UNPROTECTED_CSV,
          },
          {
            dataset_name: 'synthetic_alumni_clean.json',
            raw_content: PRESET_PROTECTED_JSON,
          },
        ],
      }
      const res = await fetch(PIPELINE_BATCH_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      setBatchResult(data)
      fetchRuns()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error running batch validation')
    } finally {
      setLoading(false)
    }
  }

  // Load report modal
  const handleViewReport = async (pipelineId: string) => {
    try {
      const res = await fetch(PIPELINE_REPORT_URL(pipelineId))
      if (res.ok) {
        const data = await res.json()
        setReportModal(data)
      }
    } catch {
      setErrorMsg('Failed to fetch pipeline verification report')
    }
  }

  // KPI Calculations
  const totalRuns = runsList.length
  const readyRuns = runsList.filter((r) => r.status === 'READY' || r.status === 'PUBLISHED').length
  const blockedRuns = runsList.filter((r) => r.status === 'BLOCKED').length
  const failedRuns = runsList.filter((r) => r.status === 'FAILED').length

  const getStatusBadge = (st: PipelineState) => {
    switch (st) {
      case 'READY':
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">READY</span>
      case 'PUBLISHED':
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">PUBLISHED</span>
      case 'BLOCKED':
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-500/20 text-red-300 border border-red-500/30">BLOCKED</span>
      case 'FAILED':
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">FAILED</span>
      default:
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-slate-700 text-slate-300">{st}</span>
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">⚡</span>
            <h1 className="text-xl font-bold text-white tracking-wide">
              Pipeline Monitor &amp; Security Gate
            </h1>
            <span className="px-2 py-0.5 text-[10px] font-bold bg-blue-500/20 text-blue-300 rounded border border-blue-500/30">
              Phase 10
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Automated sensitive-field discovery, masking policy validation, and fail-closed publication gate for external analytics workflows.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('single')}
            className={`px-3 py-1.5 rounded text-xs font-semibold transition-all ${
              activeTab === 'single'
                ? 'bg-blue-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Pipeline Validator
          </button>
          <button
            onClick={() => setActiveTab('batch')}
            className={`px-3 py-1.5 rounded text-xs font-semibold transition-all ${
              activeTab === 'batch'
                ? 'bg-blue-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Batch Processing
          </button>
          <button
            onClick={() => {
              setActiveTab('history')
              fetchRuns()
            }}
            className={`px-3 py-1.5 rounded text-xs font-semibold transition-all ${
              activeTab === 'history'
                ? 'bg-blue-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Execution Ledger ({totalRuns})
          </button>
        </div>
      </div>

      {/* Phase 11 Production Hardening & Scalability Status Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-semibold text-slate-300">Orchestration:</span>
            <span className="text-emerald-400 font-mono font-bold uppercase">{readyStatus?.status || 'READY'}</span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-300">Auth Mode:</span>
            <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono border border-blue-500/30">
              {readyStatus?.auth_mode || 'DEMO_ROLE_SWITCHER'}
            </span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-300">Worker Queue:</span>
            <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono border border-purple-500/30">
              {workerStats ? `${workerStats.concurrency} Workers (${workerStats.status})` : 'In-Process (4 Workers)'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">Formats:</span>
          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">CSV</span>
          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">JSON</span>
          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">PARQUET</span>
          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">ARROW</span>
          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">ORC</span>
          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">AVRO</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Validations</p>
          <p className="text-2xl font-black text-white mt-1">{totalRuns}</p>
          <p className="text-[10px] text-slate-500 mt-1">Sourced from SQLite pipeline_runs</p>
        </div>
        <div className="card p-4 bg-slate-900/60 border border-emerald-900/30 rounded-xl">
          <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">Safe / Ready</p>
          <p className="text-2xl font-black text-emerald-300 mt-1">{readyRuns}</p>
          <p className="text-[10px] text-emerald-500/80 mt-1">Passed policy &amp; RBAC checks</p>
        </div>
        <div className="card p-4 bg-slate-900/60 border border-red-900/30 rounded-xl">
          <p className="text-[11px] font-bold uppercase tracking-wider text-red-400">Security Blocked</p>
          <p className="text-2xl font-black text-red-300 mt-1">{blockedRuns}</p>
          <p className="text-[10px] text-red-500/80 mt-1">Fail-closed gate triggered</p>
        </div>
        <div className="card p-4 bg-slate-900/60 border border-amber-900/30 rounded-xl">
          <p className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Schema Errors</p>
          <p className="text-2xl font-black text-amber-300 mt-1">{failedRuns}</p>
          <p className="text-[10px] text-amber-500/80 mt-1">Corrupt CSV/JSON payloads</p>
        </div>
      </div>

      {/* Error alert if any */}
      {errorMsg && (
        <div className="p-3 bg-red-900/20 border border-red-500/40 rounded-lg text-xs text-red-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white text-sm">✕</button>
        </div>
      )}

      {/* TAB 1: Single Pipeline Validator */}
      {activeTab === 'single' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Ingestion & Settings */}
          <div className="lg:col-span-5 space-y-4">
            <div className="card p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>📥</span> Pipeline Dataset Ingestion
              </h2>

              {/* Preset Selector */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                  Load Synthetic Preset
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setRawContent(PRESET_UNPROTECTED_CSV)
                      setDatasetName('unprotected_student_admissions.csv')
                    }}
                    className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 rounded font-semibold text-center border border-slate-700"
                  >
                    Unsafe CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setRawContent(PRESET_PROTECTED_JSON)
                      setDatasetName('protected_alumni_dataset.json')
                    }}
                    className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 rounded font-semibold text-center border border-slate-700"
                  >
                    Protected JSON
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setRawContent(PRESET_CORRUPT_CSV)
                      setDatasetName('corrupt_dataset.csv')
                    }}
                    className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 rounded font-semibold text-center border border-slate-700"
                  >
                    Corrupt Payload
                  </button>
                </div>
              </div>

              {/* Dataset Name */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Dataset Identifier
                </label>
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Target Destination */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Analytics Destination
                </label>
                <input
                  type="text"
                  value={targetDestination}
                  onChange={(e) => setTargetDestination(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Requesting Role */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Requesting Pipeline Role
                </label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as DemoRole)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-cyan-300 font-semibold focus:outline-none focus:border-blue-500 cursor-pointer"
                >
                  <option value="DATA_ENGINEER">DATA_ENGINEER (Validate only)</option>
                  <option value="ANALYST">ANALYST (Publish permitted)</option>
                  <option value="SECURITY_ADMIN">SECURITY_ADMIN (Full control)</option>
                  <option value="FACULTY">FACULTY (Denied publication)</option>
                  <option value="PLACEMENT_ADMIN">PLACEMENT_ADMIN (Controlled)</option>
                </select>
              </div>

              {/* Raw Dataset Payload */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Raw Synthetic Content (CSV or JSON)
                </label>
                <textarea
                  rows={6}
                  value={rawContent}
                  onChange={(e) => setRawContent(e.target.value)}
                  placeholder="Paste synthetic CSV or JSON content..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Adversarial client assertion test */}
              <div className="flex items-center gap-2 p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg">
                <input
                  type="checkbox"
                  id="clientApprovedCheck"
                  checked={clientApproved}
                  onChange={(e) => setClientApproved(e.target.checked)}
                  className="rounded border-slate-700 text-blue-600 focus:ring-0 cursor-pointer"
                />
                <label htmlFor="clientApprovedCheck" className="text-[11px] text-slate-400 cursor-pointer">
                  Assert client-side <span className="font-mono text-amber-300">approved=true</span> (Backend must independently reject)
                </label>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={handlePreview}
                  disabled={loading}
                  className="px-3 py-2.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-bold rounded-lg border border-slate-700 transition-all flex items-center justify-center gap-1.5"
                >
                  👁️ Preview
                </button>
                <button
                  type="button"
                  onClick={handleValidate}
                  disabled={loading}
                  className="flex-1 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow transition-all flex items-center justify-center gap-1.5"
                >
                  {loading ? 'Evaluating Gate…' : '🛡️ Validate Pipeline Gate'}
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Gate Decision & Results */}
          <div className="lg:col-span-7 space-y-4">
            {validateResult ? (
              <div className="card p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-5">
                {/* Decision Header */}
                <div className={`p-4 rounded-xl border flex items-center justify-between ${
                  validateResult.decision === 'ALLOW'
                    ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                    : 'bg-red-950/30 border-red-500/40 text-red-200'
                }`}>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xl">
                        {validateResult.decision === 'ALLOW' ? '🟢' : '🔴'}
                      </span>
                      <h3 className="font-extrabold text-base tracking-wide">
                        PUBLICATION GATE: {validateResult.decision}
                      </h3>
                      {getStatusBadge(validateResult.status)}
                    </div>
                    <p className="text-xs mt-1 text-slate-300">
                      {validateResult.message}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Risk Score</span>
                    <span className="text-xl font-black text-white">{validateResult.risk_score}/100</span>
                    <span className={`block text-[10px] font-bold ${
                      validateResult.risk_level === 'CRITICAL' || validateResult.risk_level === 'HIGH'
                        ? 'text-red-400'
                        : 'text-emerald-400'
                    }`}>
                      {validateResult.risk_level} RISK
                    </span>
                  </div>
                </div>

                {/* Sub-Check Matrix */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg">
                    <span className="text-[10px] uppercase font-bold text-slate-500 block">Detection</span>
                    <span className={`text-xs font-bold ${validateResult.detection_status === 'PASS' ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {validateResult.detection_status}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      {validateResult.sensitive_fields.length} sensitive fields
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg">
                    <span className="text-[10px] uppercase font-bold text-slate-500 block">Masking Policy</span>
                    <span className={`text-xs font-bold ${validateResult.policy_status === 'PASS' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {validateResult.policy_status}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      {validateResult.policy_violations.length} violations
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg">
                    <span className="text-[10px] uppercase font-bold text-slate-500 block">Authorization</span>
                    <span className={`text-xs font-bold ${validateResult.authorization_status === 'PASS' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {validateResult.authorization_status}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      Role: {validateResult.role}
                    </span>
                  </div>
                </div>

                {/* Policy Violations (if any) */}
                {validateResult.policy_violations.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-red-400 uppercase tracking-wider flex items-center gap-1.5">
                      <span>⛔</span> Policy Violations ({validateResult.policy_violations.length})
                    </h4>
                    <div className="space-y-1.5">
                      {validateResult.policy_violations.map((v, i) => (
                        <div key={i} className="p-2.5 bg-red-950/20 border border-red-900/40 rounded-lg text-xs flex items-center justify-between">
                          <div>
                            <span className="font-mono font-bold text-red-300">{v.field}</span>
                            <span className="text-[11px] text-slate-400 ml-2">({v.classification})</span>
                            <p className="text-[11px] text-slate-400 mt-0.5">{v.reason}</p>
                          </div>
                          <span className="px-2 py-0.5 text-[10px] font-bold bg-red-500/20 text-red-300 rounded border border-red-500/30">
                            Req: {v.required_action}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommended Actions & Masking Preview */}
                {validateResult.masking_previews.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
                      <span>✨</span> Automated Masking Preview (Phase 10)
                    </h4>
                    <div className="overflow-x-auto border border-slate-800 rounded-lg">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-950 text-slate-400 text-[10px] uppercase font-bold border-b border-slate-800">
                          <tr>
                            <th className="p-2.5">Field</th>
                            <th className="p-2.5">Classification</th>
                            <th className="p-2.5">Required Policy</th>
                            <th className="p-2.5">Transformed Preview</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                          {validateResult.masking_previews.map((m, idx) => (
                            <tr key={idx} className="hover:bg-slate-800/30">
                              <td className="p-2.5 text-white font-bold">{m.field}</td>
                              <td className="p-2.5 text-slate-400">{m.classification}</td>
                              <td className="p-2.5">
                                <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-300 rounded text-[10px]">
                                  {m.required_policy}
                                </span>
                              </td>
                              <td className="p-2.5 text-emerald-300 truncate max-w-[200px]">{m.preview}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Audit & Report Metadata */}
                <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 text-[10px]">Audit Reference:</span>
                    <span className="font-mono text-[10px] text-cyan-400 truncate max-w-[160px]">
                      {validateResult.audit_reference || 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleViewReport(validateResult.pipeline_id)}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded border border-slate-700"
                    >
                      📄 View Full Report
                    </button>
                    {validateResult.decision === 'ALLOW' && validateResult.status !== 'PUBLISHED' && (
                      <button
                        type="button"
                        onClick={handlePublish}
                        disabled={loading}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded shadow transition-all"
                      >
                        🚀 Execute Publication
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="card p-12 bg-slate-900/40 border border-slate-800/60 rounded-xl text-center space-y-3">
                <span className="text-4xl block">🛡️</span>
                <h3 className="text-sm font-bold text-white">No Pipeline Run Active</h3>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  Configure synthetic dataset ingestion on the left and click <span className="text-blue-400 font-semibold">Validate Pipeline Gate</span> to trigger schema extraction, sensitive-field detection, and fail-closed publication checks.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Batch Processing */}
      {activeTab === 'batch' && (
        <div className="card p-6 bg-slate-900/80 border border-slate-800 rounded-xl space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>📦</span> Synthetic Batch Pipeline Validation
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluates multiple analytical datasets simultaneously. Employs rigid fail-closed semantics: if any dataset is blocked, the entire batch status is marked BLOCKED.
              </p>
            </div>
            <button
              type="button"
              onClick={handleRunBatch}
              disabled={loading}
              className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold rounded-lg shadow"
            >
              {loading ? 'Running Batch…' : '⚡ Execute Batch Validation'}
            </button>
          </div>

          {batchResult && (
            <div className="space-y-4">
              {/* Batch Summary Card */}
              <div className={`p-4 rounded-xl border flex items-center justify-between ${
                batchResult.summary.overall_decision === 'ALLOW'
                  ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                  : 'bg-red-950/30 border-red-500/40 text-red-200'
              }`}>
                <div>
                  <h3 className="text-base font-extrabold flex items-center gap-2">
                    <span>{batchResult.summary.overall_decision === 'ALLOW' ? '🟢' : '🔴'}</span>
                    Batch Result: {batchResult.summary.overall_decision}
                  </h3>
                  <p className="text-xs text-slate-300 mt-1">
                    Batch ID: <span className="font-mono">{batchResult.batch_id}</span> •{' '}
                    {batchResult.summary.fail_closed_triggered
                      ? 'Fail-closed protection triggered due to unmasked dataset violations.'
                      : 'All datasets in batch successfully verified.'}
                  </p>
                </div>
                <div className="flex gap-4 text-right">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Total</span>
                    <span className="text-lg font-black text-white">{batchResult.summary.total_datasets}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-400 block">Passed</span>
                    <span className="text-lg font-black text-emerald-300">{batchResult.summary.passed}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-red-400 block">Blocked</span>
                    <span className="text-lg font-black text-red-300">{batchResult.summary.blocked}</span>
                  </div>
                </div>
              </div>

              {/* Datasets Breakdown */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Individual Dataset Results
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {batchResult.results.map((r, i) => (
                    <div key={i} className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-white">{r.dataset_name}</span>
                        {getStatusBadge(r.status)}
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span>Risk: {r.risk_level} ({r.risk_score}/100)</span>
                        <span>Violations: {r.policy_violations.length}</span>
                      </div>
                      <p className="text-[10px] text-slate-500 truncate">{r.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Execution Ledger */}
      {activeTab === 'history' && (
        <div className="card p-6 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span>📋</span> Pipeline Execution Ledger (Zero-PII Storage)
            </h2>
            <button
              onClick={fetchRuns}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-semibold"
            >
              🔄 Refresh
            </button>
          </div>

          <div className="overflow-x-auto border border-slate-800 rounded-lg">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 text-[10px] uppercase font-bold border-b border-slate-800">
                <tr>
                  <th className="p-3">Pipeline ID</th>
                  <th className="p-3">Dataset</th>
                  <th className="p-3">Format</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Decision</th>
                  <th className="p-3">Risk Level</th>
                  <th className="p-3">Audit Reference</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {runsList.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-800/30">
                    <td className="p-3 font-bold text-white">{run.pipeline_id}</td>
                    <td className="p-3 text-slate-300 font-sans">{run.dataset_name}</td>
                    <td className="p-3 text-slate-400">{run.format}</td>
                    <td className="p-3 text-cyan-300">{run.role}</td>
                    <td className="p-3">{getStatusBadge(run.status)}</td>
                    <td className="p-3 font-bold">
                      <span className={run.decision === 'ALLOW' ? 'text-emerald-400' : 'text-red-400'}>
                        {run.decision}
                      </span>
                    </td>
                    <td className="p-3 text-slate-400 font-sans">{run.risk_level} ({run.risk_score})</td>
                    <td className="p-3 text-slate-500 truncate max-w-[120px]">
                      {run.audit_reference || 'N/A'}
                    </td>
                    <td className="p-3 text-right font-sans">
                      <button
                        onClick={() => handleViewReport(run.pipeline_id)}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-blue-400 text-[11px] rounded border border-slate-700 font-semibold"
                      >
                        Report
                      </button>
                    </td>
                  </tr>
                ))}
                {runsList.length === 0 && (
                  <tr>
                    <td colSpan={9} className="p-6 text-center text-slate-500 font-sans">
                      No pipeline runs recorded yet. Execute a validation above to populate the ledger.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Report Modal */}
      {reportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="card p-6 bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full max-h-[80vh] flex flex-col space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>📄</span> Pipeline Verification Report: {reportModal.pipeline_id}
              </h3>
              <button
                onClick={() => setReportModal(null)}
                className="text-slate-400 hover:text-white text-base"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap">
              {reportModal.markdown_report}
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setReportModal(null)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
