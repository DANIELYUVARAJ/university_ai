import { useState, useCallback } from 'react'
import type { ScanResponse, ScanRequest, Classification } from '../types'
import { SCAN_URL, SCHEMA_URL } from '../config'
import {
  ClassificationBadge,
  ConfidenceBar,
  SignalDots,
} from '../components/ScanResultBadges'

type ScanState = 'idle' | 'loading' | 'done' | 'error'

// ── Summary stat card ─────────────────────────────────────────────────────────

function StatPill({
  label,
  value,
  color,
  subtext,
}: {
  label: string
  value: number | string
  color: string
  subtext?: string
}) {
  return (
    <div className={`rounded-xl border px-4 py-3 text-center ${color}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-[11px] text-slate-400 mt-0.5 font-medium">{label}</p>
      {subtext && <p className="text-[10px] text-slate-500 mt-0.5">{subtext}</p>}
    </div>
  )
}

// ── Reasons / Contextual Tooltip Cell ──────────────────────────────────────────

function ReasonsCell({
  reasons,
  contextualSignals,
}: {
  reasons: string[]
  contextualSignals?: string[]
}) {
  const [open, setOpen] = useState(false)
  const hasContext = Boolean(contextualSignals && contextualSignals.length > 0)
  const allItems = [...reasons, ...(contextualSignals ?? [])]

  if (allItems.length === 0) return <span className="text-slate-600 text-xs">—</span>

  return (
    <div>
      <div className="flex items-center gap-1.5 flex-wrap">
        <button
          onClick={() => setOpen(v => !v)}
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors text-left"
        >
          {allItems[0]}
          {allItems.length > 1 && (
            <span className="ml-1 text-slate-500">+{allItems.length - 1} more {open ? '▲' : '▼'}</span>
          )}
        </button>
        {hasContext && (
          <span className="badge bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 text-[9px] px-1 py-0">
            Context
          </span>
        )}
      </div>
      {open && allItems.length > 1 && (
        <ul className="mt-1.5 space-y-1">
          {reasons.slice(1).map((r, i) => (
            <li key={`reason-${i}`} className="text-[11px] text-slate-400 pl-2 border-l border-slate-700">
              {r}
            </li>
          ))}
          {contextualSignals?.map((cs, i) => (
            <li key={`ctx-${i}`} className="text-[11px] text-cyan-300 pl-2 border-l border-cyan-500/50">
              🌐 {cs}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Recommendation Badge Cell ─────────────────────────────────────────────────

function RecommendationCell({ rec }: { rec?: string }) {
  if (!rec) return <span className="text-slate-600 text-xs">—</span>
  const isHash = rec.startsWith('HASH')
  const isMask = rec.startsWith('MASK')
  const isGen = rec.startsWith('GENERALIZE')
  const isReview = rec.startsWith('REVIEW')

  let badgeColor = 'bg-slate-700/40 text-slate-400 border-slate-600/40'
  if (isHash) badgeColor = 'bg-purple-500/15 text-purple-300 border-purple-500/30'
  if (isMask) badgeColor = 'bg-blue-500/15 text-blue-300 border-blue-500/30'
  if (isGen) badgeColor = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (isReview) badgeColor = 'bg-amber-500/20 text-amber-300 border-amber-500/40 font-bold'

  return (
    <div className="max-w-xs" title={rec}>
      <span className={`badge text-[11px] border font-medium ${badgeColor} py-1 px-2 leading-relaxed`}>
        {rec}
      </span>
    </div>
  )
}

// ── Filters ───────────────────────────────────────────────────────────────────

type CategoryFilter = 'ALL' | Classification
type StatusFilter = 'ALL' | 'REVIEW' | 'CLEAR'

const CATEGORY_FILTERS: { value: CategoryFilter; label: string }[] = [
  { value: 'ALL',                label: 'All Fields' },
  { value: 'DIRECT_IDENTIFIER',  label: 'Direct ID' },
  { value: 'QUASI_IDENTIFIER',   label: 'Quasi ID' },
  { value: 'SENSITIVE_ATTRIBUTE',label: 'Sensitive' },
  { value: 'ACADEMIC_DATA',      label: 'Academic' },
  { value: 'PLACEMENT_DATA',     label: 'Placement' },
  { value: 'NON_SENSITIVE',      label: 'Non-Sensitive' },
]

export default function DatasetScanner() {
  const [state, setState] = useState<ScanState>('idle')
  const [result, setResult] = useState<ScanResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [catFilter, setCatFilter] = useState<CategoryFilter>('ALL')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')

  const runScan = useCallback(async () => {
    setState('loading')
    setError(null)
    setResult(null)

    try {
      const schemaRes = await fetch(SCHEMA_URL)
      if (!schemaRes.ok) throw new Error(`Schema fetch failed: HTTP ${schemaRes.status}`)
      const schema: ScanRequest = await schemaRes.json()

      const scanRes = await fetch(SCAN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(schema),
      })
      if (!scanRes.ok) {
        const body = await scanRes.text()
        throw new Error(`Scan failed: HTTP ${scanRes.status} — ${body}`)
      }

      const data: ScanResponse = await scanRes.json()
      setResult(data)
      setState('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setState('error')
    }
  }, [])

  const filtered = result?.results.filter(r => {
    const matchCat = catFilter === 'ALL' || r.classification === catFilter
    const matchStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'REVIEW' && r.ambiguity_status === 'REVIEW') ||
      (statusFilter === 'CLEAR' && r.ambiguity_status === 'CLEAR')
    return matchCat && matchStatus
  }) ?? []

  const sensitiveCount = result?.sensitive_count ?? 0
  const directCount = result?.results.filter(r => r.classification === 'DIRECT_IDENTIFIER').length ?? 0
  const quasiCount  = result?.results.filter(r => r.classification === 'QUASI_IDENTIFIER').length ?? 0
  const reviewCount = result?.results.filter(r => r.ambiguity_status === 'REVIEW').length ?? 0

  return (
    <main className="flex-1 overflow-y-auto px-8 py-8">
      {/* Header */}
      <div className="mb-6 animate-fade-in-up opacity-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Phase 9 · Live
          </span>
          <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20">
            🔬 Synthetic Data Only
          </span>
          <span className="badge bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            Context-Aware Intelligence
          </span>
        </div>
        <h1 className="text-2xl font-bold text-white">Dataset Scanner &amp; Intelligence</h1>
        <p className="mt-1 text-sm text-slate-400">
          Scan dataset schemas for sensitive attributes with multi-signal discovery, field-name normalization,
          cross-field contextual reasoning, ambiguity detection, and dataset-level risk scoring.
        </p>
      </div>

      {/* Scan controls */}
      <div className="card p-5 mb-6 animate-fade-in-up opacity-0 animate-delay-100">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-semibold text-white mb-0.5">University Synthetic Dataset Schema</p>
            <p className="text-xs text-slate-500">
              Evaluates field normalization, regex patterns, contextual clusters, and recommendations · No real personal data
            </p>
          </div>
          <button
            id="scan-btn"
            onClick={runScan}
            disabled={state === 'loading'}
            className={`
              flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold
              transition-all duration-200
              ${state === 'loading'
                ? 'bg-blue-600/40 text-blue-300 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30'
              }
            `}
          >
            {state === 'loading' ? (
              <>
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Scanning with Phase 9 Intelligence…
              </>
            ) : (
              <>🔍 SCAN DATASET</>
            )}
          </button>
        </div>

        {/* Phase 9 Detection Signals bar */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { icon: '🔤', label: 'Field Normalization', color: 'text-blue-400' },
            { icon: '🔎', label: 'Pattern Intelligence', color: 'text-purple-400' },
            { icon: '📐', label: 'Data-Type Signal', color: 'text-cyan-400' },
            { icon: '🌐', label: 'Cross-Field Context', color: 'text-emerald-400' },
            { icon: '⚖️', label: 'Ambiguity & Review', color: 'text-amber-400' },
          ].map(s => (
            <div key={s.label} className="rounded-lg bg-white/3 border border-[rgb(var(--border-col))] px-3 py-2">
              <p className={`text-xs font-medium ${s.color}`}>{s.icon} {s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Error state */}
      {state === 'error' && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4">
          <p className="text-sm font-semibold text-red-400">⚠ Scan Failed</p>
          <p className="text-xs text-slate-400 mt-1">{error}</p>
          <p className="text-xs text-slate-600 mt-1">
            Make sure the backend is running on <code className="font-mono">localhost:8000</code>
          </p>
        </div>
      )}

      {/* Results */}
      {state === 'done' && result && (
        <div className="animate-fade-in-up opacity-0 space-y-6">

          {/* Dataset Risk Summary Card (Phase 9) */}
          {result.dataset_risk && (
            <div className="card p-5 border border-cyan-500/30 bg-gradient-to-r from-slate-900/90 to-slate-800/90">
              <div className="flex items-center justify-between flex-wrap gap-4 mb-4 pb-3 border-b border-slate-700/50">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🛡️</span>
                    <h2 className="text-base font-bold text-white">Dataset-Level Risk Summary</h2>
                    <span className="badge bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 text-xs">
                      Phase 9 Intelligence
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Synthetic schema composition risk analysis and publication readiness
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-[10px] uppercase font-bold text-slate-400">Publication Readiness</p>
                    <span className={`badge text-xs font-bold border ${
                      result.dataset_risk.publication_readiness === 'READY'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}>
                      {result.dataset_risk.publication_readiness === 'READY' ? '🟢 READY FOR PUBLICATION' : '🟡 NEEDS PROTECTION'}
                    </span>
                  </div>

                  <div className="text-right pl-3 border-l border-slate-700">
                    <p className="text-[10px] uppercase font-bold text-slate-400">Dataset Risk Level</p>
                    <span className={`badge text-xs font-bold border ${
                      result.dataset_risk.risk_level === 'CRITICAL' ? 'bg-red-600/30 text-red-300 border-red-500/50' :
                      result.dataset_risk.risk_level === 'HIGH' ? 'bg-red-500/20 text-red-400 border-red-500/40' :
                      result.dataset_risk.risk_level === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400 border-amber-500/40' :
                      'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    }`}>
                      {result.dataset_risk.risk_level} ({result.dataset_risk.risk_score} / 100)
                    </span>
                  </div>
                </div>
              </div>

              {/* Risk Factors breakdown */}
              {result.dataset_risk.risk_factors.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-semibold text-slate-300 mb-1.5">Identified Risk Factors:</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {result.dataset_risk.risk_factors.map((rf, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs text-slate-300 bg-slate-800/60 rounded px-2.5 py-1.5 border border-slate-700/60">
                        <span className="text-amber-400">⚠️</span>
                        <span>{rf}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-[10px] text-slate-500 italic mt-2">
                * {result.dataset_risk.disclaimer}
              </p>
            </div>
          )}

          {/* Summary stats */}
          <div>
            <p className="section-title mb-3">Scan Overview · {result.dataset_name}</p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <StatPill
                label="Fields Scanned"
                value={result.fields_scanned}
                color="border-[rgb(var(--border-col))] text-white"
              />
              <StatPill
                label="Sensitive Fields"
                value={sensitiveCount}
                color="border-red-500/30 text-red-300"
              />
              <StatPill
                label="Direct Identifiers"
                value={directCount}
                color="border-red-500/20 text-red-400"
              />
              <StatPill
                label="Quasi Identifiers"
                value={quasiCount}
                color="border-orange-500/20 text-orange-400"
              />
              <StatPill
                label="Review / Ambiguous"
                value={reviewCount}
                color="border-amber-500/30 text-amber-300"
                subtext="Requires verification"
              />
            </div>
          </div>

          {/* Filter Pills */}
          <div className="space-y-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex flex-wrap gap-2">
                {CATEGORY_FILTERS.map(f => {
                  const count = f.value === 'ALL'
                    ? result.results.length
                    : result.results.filter(r => r.classification === f.value).length
                  return (
                    <button
                      key={f.value}
                      onClick={() => setCatFilter(f.value)}
                      className={`badge border transition-all ${
                        catFilter === f.value
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-slate-700/40 text-slate-400 border-slate-600/50 hover:border-slate-500'
                      }`}
                    >
                      {f.label}
                      <span className={`ml-1 text-[10px] ${catFilter === f.value ? 'text-blue-200' : 'text-slate-600'}`}>
                        {count}
                      </span>
                    </button>
                  )
                })}
              </div>

              {/* Status filter: Review vs Clear */}
              <div className="flex items-center gap-1.5 bg-slate-900/80 border border-slate-700 rounded-lg p-1 text-xs">
                <span className="text-[10px] text-slate-400 px-1 font-semibold uppercase">Ambiguity:</span>
                <button
                  onClick={() => setStatusFilter('ALL')}
                  className={`px-2 py-0.5 rounded text-xs transition-colors ${
                    statusFilter === 'ALL' ? 'bg-slate-700 text-white font-medium' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  All ({result.results.length})
                </button>
                <button
                  onClick={() => setStatusFilter('REVIEW')}
                  className={`px-2 py-0.5 rounded text-xs transition-colors ${
                    statusFilter === 'REVIEW' ? 'bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40' : 'text-slate-400 hover:text-amber-300'
                  }`}
                >
                  Review ({reviewCount})
                </button>
                <button
                  onClick={() => setStatusFilter('CLEAR')}
                  className={`px-2 py-0.5 rounded text-xs transition-colors ${
                    statusFilter === 'CLEAR' ? 'bg-emerald-500/20 text-emerald-300 font-medium' : 'text-slate-400 hover:text-emerald-300'
                  }`}
                >
                  Clear ({result.results.length - reviewCount})
                </button>
              </div>
            </div>
          </div>

          {/* Results table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[rgb(var(--border-col))] bg-white/2">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Field Name</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Normalized</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Classification</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Confidence</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Signals</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Recommendation</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Detection Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, idx) => (
                    <tr
                      key={r.field}
                      className={`border-b border-[rgb(var(--border-col))]/50 transition-colors hover:bg-white/2
                        ${idx % 2 === 0 ? '' : 'bg-white/1'}
                        ${r.ambiguity_status === 'REVIEW' ? 'bg-amber-500/5' : ''}`}
                    >
                      <td className="px-4 py-3">
                        <code className="font-mono text-xs text-slate-200 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60">
                          {r.field}
                        </code>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs text-slate-400">
                          {r.normalized_name ?? r.field.toLowerCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-400">{r.data_type}</span>
                      </td>
                      <td className="px-4 py-3">
                        <ClassificationBadge cls={r.classification} />
                      </td>
                      <td className="px-4 py-3">
                        <ConfidenceBar
                          score={r.confidence}
                          band={r.confidence_band}
                          level={r.confidence_level}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <SignalDots field={r} />
                      </td>
                      <td className="px-4 py-3">
                        <RecommendationCell rec={r.recommendation} />
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        <ReasonsCell
                          reasons={r.reasons}
                          contextualSignals={r.contextual_signals}
                        />
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-slate-600 text-sm">
                        No fields match the selected filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Scan metadata */}
          <p className="text-[11px] text-slate-600 mt-3">
            Scan ID: {result.scan_id} · {result.fields_scanned} fields processed · Multi-signal &amp; contextual analysis completed
          </p>
        </div>
      )}

      {/* Idle state hint */}
      {state === 'idle' && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[rgb(var(--border-col))] bg-[rgb(var(--bg-card))]/30 py-20 text-center">
          <div className="text-5xl mb-4 opacity-40">🔍</div>
          <p className="text-slate-300 font-medium">Ready to scan dataset schema</p>
          <p className="text-slate-500 text-sm mt-1">
            Click <strong className="text-slate-400">SCAN DATASET</strong> to execute multi-signal discovery, field normalization, and risk assessment
          </p>
        </div>
      )}
    </main>
  )
}
