import { useState, useEffect } from 'react'
import {
  ASSISTANT_STATUS_URL,
  ASSISTANT_ASK_URL,
  ASSISTANT_EXPLAIN_SCAN_URL,
} from '../config'

interface AssistantStatus {
  available: boolean
  provider: string
  model: string
  base_url: string
  message: string
  setup_instructions?: string
  advisory_notice: string
}

interface QuestionResponse {
  question: string
  provider: string
  model: string
  answer?: string
  explanation?: string
  is_advisory: boolean
  policy_engine_validated?: boolean
  warning?: string
  advisory_warning?: string
}

function formatApiError(errData: any, status: number): string {
  if (!errData) return `Server returned HTTP ${status}`
  if (typeof errData.detail === 'string') {
    return errData.detail
  }
  if (Array.isArray(errData.detail)) {
    return errData.detail
      .map((item: any) => {
        const field = Array.isArray(item.loc)
          ? item.loc.filter((part: any) => part !== 'body').join('.')
          : ''
        return field ? `${field}: ${item.msg}` : item.msg || JSON.stringify(item)
      })
      .join('; ')
  }
  if (errData.detail && typeof errData.detail === 'object') {
    return JSON.stringify(errData.detail)
  }
  if (errData.message && typeof errData.message === 'string') {
    return errData.message
  }
  return `Server returned HTTP ${status}`
}

interface FieldExplanation {
  field_name: string
  classification: string
  is_sensitive: boolean
  suggested_policy: string
  rationale: string
  deterministic_status: string
  deterministic_reason: string
  gate_impact: string
}

interface ExplainScanResponse {
  summary: string
  total_fields: number
  sensitive_fields_count: number
  publication_blocked: boolean
  blocking_reasons: string[]
  fields: FieldExplanation[]
  provider: string
  model: string
  is_advisory: boolean
  advisory_warning: string
}

const DEFAULT_SYNTHETIC_FIELDS = [
  {
    field_name: 'student_email',
    data_type: 'string',
    sample_pattern: 'student_001@university.edu',
    inferred_classification: 'DIRECT_IDENTIFIER',
    confidence: 0.98,
  },
  {
    field_name: 'attendance_percentage',
    data_type: 'numeric',
    sample_pattern: '88.5%',
    inferred_classification: 'ACADEMIC_DATA',
    confidence: 0.92,
  },
  {
    field_name: 'placement_package',
    data_type: 'numeric',
    sample_pattern: '1200000',
    inferred_classification: 'SENSITIVE_ATTRIBUTE',
    confidence: 0.89,
  },
  {
    field_name: 'student_identifier',
    data_type: 'string',
    sample_pattern: 'STU-2024-9876',
    inferred_classification: 'DIRECT_IDENTIFIER',
    confidence: 0.95,
  },
]

const EXAMPLE_QUESTIONS = [
  'Why should student_email be masked before analytics publication?',
  'Why is placement_package sensitive compensation data under university policy?',
  'What happens if student_identifier is published without hashing?',
  'Why can attendance_percentage be published without masking?',
]

export default function Assistant() {
  const [status, setStatus] = useState<AssistantStatus | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)

  // Question state
  const [question, setQuestion] = useState(
    'Why should student_email be masked before analytics publication?'
  )
  const [asking, setAsking] = useState(false)
  const [questionResult, setQuestionResult] = useState<QuestionResponse | null>(null)
  const [askError, setAskError] = useState<string | null>(null)

  // Scan explainer state
  const [explaining, setExplaining] = useState(false)
  const [scanResult, setScanResult] = useState<ExplainScanResponse | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)

  const fetchStatus = async () => {
    setLoadingStatus(true)
    try {
      const res = await fetch(ASSISTANT_STATUS_URL)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      } else {
        setStatus({
          available: false,
          provider: 'unknown',
          model: 'none',
          base_url: '',
          message: 'Failed to query assistant backend service.',
          advisory_notice: 'LLM is advisory only.',
        })
      }
    } catch {
      setStatus({
        available: false,
        provider: 'unknown',
        model: 'none',
        base_url: '',
        message: 'Could not connect to backend LLM service.',
        advisory_notice: 'LLM is advisory only.',
      })
    } finally {
      setLoadingStatus(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  const handleAsk = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!question.trim()) return

    setAsking(true)
    setAskError(null)
    setQuestionResult(null)

    try {
      const res = await fetch(ASSISTANT_ASK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: question.trim(),
          context: 'University student analytical warehouse publication review',
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        throw new Error(formatApiError(errData, res.status))
      }

      const data: QuestionResponse = await res.json()
      setQuestionResult(data)
    } catch (err: unknown) {
      setAskError(err instanceof Error ? err.message : 'Failed to query AI assistant')
    } finally {
      setAsking(false)
    }
  }

  const handleExplainScan = async () => {
    setExplaining(true)
    setScanError(null)
    setScanResult(null)

    try {
      const res = await fetch(ASSISTANT_EXPLAIN_SCAN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_name: 'synthetic_university_graduates',
          findings: DEFAULT_SYNTHETIC_FIELDS,
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        throw new Error(formatApiError(errData, res.status))
      }

      const data: ExplainScanResponse = await res.json()
      setScanResult(data)
    } catch (err: unknown) {
      setScanError(err instanceof Error ? err.message : 'Failed to explain scan findings')
    } finally {
      setExplaining(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <h1 className="text-xl font-bold text-white tracking-tight">
              DataShield AI Assistant
            </h1>
            <span className="badge bg-purple-500/10 text-purple-400 border border-purple-500/30 text-xs font-semibold">
              Advisory Demonstration
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Plain-language explanations for sensitive-field classifications, masking recommendations,
            and publication-blocking findings.
          </p>
        </div>

        <button
          onClick={fetchStatus}
          disabled={loadingStatus}
          className="self-start md:self-auto text-xs px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-750 text-slate-300 flex items-center gap-2 transition"
        >
          <span className={loadingStatus ? 'animate-spin' : ''}>🔄</span>
          {loadingStatus ? 'Checking...' : 'Refresh Status'}
        </button>
      </div>

      {/* Advisory Warning Banner */}
      <div className="bg-amber-950/30 border border-amber-600/40 rounded-xl p-4 text-xs text-amber-200/90 flex items-start gap-3 shadow-inner">
        <span className="text-base leading-none">⚠️</span>
        <div className="space-y-1">
          <p className="font-semibold text-amber-300">
            Mandatory Security Boundary Notice (Advisory Only)
          </p>
          <p className="text-amber-200/80 leading-relaxed">
            The AI Assistant provides informational guidance only. It has{' '}
            <strong className="text-white">zero authority</strong> to approve analytical publication,
            override <code className="bg-amber-900/40 px-1 py-0.5 rounded text-amber-100 font-mono">BLOCK</code> or{' '}
            <code className="bg-amber-900/40 px-1 py-0.5 rounded text-amber-100 font-mono">REVIEW</code> decisions,
            or bypass Role-Based Access Control (RBAC). All recommendations must be validated by the
            deterministic PolicyEngine.
          </p>
        </div>
      </div>

      {/* Status Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-200">Local LLM Service Status:</span>
            {status?.available ? (
              <span className="badge bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Ollama Active ({status.model})
              </span>
            ) : (
              <span className="badge bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                Ollama Unavailable (Deterministic Fallback Active)
              </span>
            )}
          </div>
          <span className="text-[11px] text-slate-500 font-mono">Provider: {status?.provider || 'probing...'}</span>
        </div>

        {status && !status.available && (
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 space-y-2 mt-2">
            <p className="text-slate-300 font-medium">ℹ️ {status.message}</p>
            {status.setup_instructions && (
              <div className="space-y-1">
                <p className="text-slate-400 text-[11px]">To run a local Ollama model for college demo:</p>
                <div className="bg-slate-900 p-2.5 rounded font-mono text-[11px] text-cyan-300 border border-slate-800 select-all overflow-x-auto">
                  {status.setup_instructions}
                </div>
              </div>
            )}
            <p className="text-slate-400 text-[11px]">
              🛡️ <span className="text-slate-300 font-semibold">Self-Sustaining Mode:</span> When Ollama is offline,
              DataShield uses its internal deterministic knowledge base and active PolicyEngine to answer queries and
              explain scans accurately without fabricating AI hallucinations.
            </p>
          </div>
        )}
      </div>

      {/* Grid: Question Panel & Synthetic Scan Explainer */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Ask Assistant */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div className="space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>💬</span> Ask DataShield Assistant
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Ask about sensitive-field detection, FERPA compliance, and masking rationale.
              </p>
            </div>

            {/* Example prompt pills */}
            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Preset Viva / Demo Questions:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {EXAMPLE_QUESTIONS.map((q, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setQuestion(q)}
                    className="text-[11px] text-left px-2.5 py-1 rounded bg-slate-800/90 hover:bg-slate-750 text-cyan-300/90 border border-slate-700/60 transition"
                  >
                    "{q}"
                  </button>
                ))}
              </div>
            </div>

            {/* Input Form */}
            <form onSubmit={handleAsk} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Question (Max 1,000 characters):
                </label>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  rows={3}
                  maxLength={1000}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-sans resize-none"
                  placeholder="e.g. Why should student_email be masked before analytics publication?"
                />
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  {question.length}/1000 chars • Zero raw PII transmitted
                </span>
                <button
                  type="submit"
                  disabled={asking || !question.trim()}
                  className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow transition"
                >
                  {asking ? (
                    <>
                      <span className="animate-spin">🌀</span> Consulting...
                    </>
                  ) : (
                    <>
                      <span>🔍</span> Ask Assistant
                    </>
                  )}
                </button>
              </div>
            </form>

            {askError && (
              <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-300">
                ❌ {askError}
              </div>
            )}

            {/* Question Response Card */}
            {questionResult && (
              <div className="bg-slate-950/90 border border-cyan-900/40 rounded-xl p-4 space-y-3 shadow-inner">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="text-xs font-semibold text-cyan-400">
                    Assistant Rationale ({questionResult.provider})
                  </span>
                  <span className="badge bg-cyan-500/10 text-cyan-300 text-[10px] border border-cyan-500/20">
                    {questionResult.policy_engine_validated ? 'Policy Engine Verified' : 'Advisory Note'}
                  </span>
                </div>

                <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-line bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                  {questionResult.explanation || questionResult.answer}
                </div>

                <div className="flex items-center gap-1.5 text-[10px] text-amber-300/80 bg-amber-950/20 px-2.5 py-1.5 rounded border border-amber-800/30">
                  <span>⚠️</span>
                  <span>{questionResult.warning || questionResult.advisory_warning}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Explain Synthetic Scan */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div className="space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>📋</span> Synthetic Schema Scan Explainer
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Generate plain-language explanations of sensitive findings and publication gate verdicts.
              </p>
            </div>

            {/* Synthetic schema details */}
            <div className="space-y-2">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Synthetic Test Schema (Pre-Loaded Demo Fields):
              </p>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                {DEFAULT_SYNTHETIC_FIELDS.map((f, i) => (
                  <div
                    key={i}
                    className="bg-slate-950/80 p-2 rounded-lg border border-slate-800 flex flex-col justify-between"
                  >
                    <span className="font-mono text-cyan-300 font-semibold">{f.field_name}</span>
                    <span className="text-[10px] text-slate-400 mt-1">
                      {f.inferred_classification} ({Math.round(f.confidence * 100)}% conf)
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={handleExplainScan}
                disabled={explaining}
                className="w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 shadow transition"
              >
                {explaining ? (
                  <>
                    <span className="animate-spin">🌀</span> Analyzing Synthetic Schema...
                  </>
                ) : (
                  <>
                    <span>⚡</span> Explain Findings from Completed Scan
                  </>
                )}
              </button>
            </div>

            {scanError && (
              <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-300">
                ❌ {scanError}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Full-width Scan Findings Report */}
      {scanResult && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>🛡️</span> Scan Findings &amp; Publication Gate Assessment
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluation generated via {scanResult.provider} ({scanResult.model})
              </p>
            </div>

            <div className="flex items-center gap-3">
              {scanResult.publication_blocked ? (
                <span className="badge bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-bold px-3 py-1 flex items-center gap-1.5">
                  🛑 Publication Gate: BLOCKED (Fail-Closed)
                </span>
              ) : (
                <span className="badge bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold px-3 py-1 flex items-center gap-1.5">
                  ✅ Publication Gate: ALLOW
                </span>
              )}
            </div>
          </div>

          {/* Plain Language Summary */}
          <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Executive Findings Summary:
            </p>
            <p className="text-xs text-slate-200 leading-relaxed">{scanResult.summary}</p>
            {scanResult.blocking_reasons.length > 0 && (
              <div className="pt-2 border-t border-slate-850">
                <p className="text-[11px] font-semibold text-red-400 mb-1">
                  Enforced Blocking Reasons:
                </p>
                <ul className="list-disc list-inside text-xs text-slate-300 space-y-0.5">
                  {scanResult.blocking_reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Comparison Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300 border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/60 text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="py-2.5 px-3">Field Name</th>
                  <th className="py-2.5 px-3">Inferred Classification</th>
                  <th className="py-2.5 px-3">Suggested Policy</th>
                  <th className="py-2.5 px-3">Deterministic Engine Status</th>
                  <th className="py-2.5 px-3">Gate Verdict</th>
                  <th className="py-2.5 px-3">Sensitivity Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {scanResult.fields.map((f, i) => (
                  <tr key={i} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3 font-mono text-cyan-300 font-semibold">{f.field_name}</td>
                    <td className="py-3 px-3">
                      <span className="badge bg-slate-800 text-slate-300 border border-slate-700 text-[10px]">
                        {f.classification}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="badge bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[11px] font-mono font-bold">
                        {f.suggested_policy}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      {f.deterministic_status === 'VERIFIED_COMPLIANT' ? (
                        <span className="text-emerald-400 font-medium flex items-center gap-1">
                          <span>✓</span> Verified Compliant
                        </span>
                      ) : (
                        <span className="text-amber-400 font-medium flex items-center gap-1">
                          <span>⚠️</span> {f.deterministic_status}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {f.gate_impact === 'BLOCK' ? (
                        <span className="text-red-400 font-bold bg-red-950/40 px-2 py-0.5 rounded border border-red-800/60 text-[11px]">
                          BLOCK
                        </span>
                      ) : (
                        <span className="text-emerald-400 font-bold bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/60 text-[11px]">
                          ALLOW
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-400 text-[11px] leading-relaxed max-w-sm">
                      {f.rationale}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer Notice */}
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
            <span>🛡️ Deterministic Policy Engine v1.0 enforced authoritative validation.</span>
            <span className="text-slate-500">{scanResult.advisory_warning}</span>
          </div>
        </div>
      )}
    </div>
  )
}
