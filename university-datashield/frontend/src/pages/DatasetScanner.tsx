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
}: {
  label: string
  value: number | string
  color: string
}) {
  return (
    <div className={`rounded-xl border px-4 py-3 text-center ${color}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-[11px] text-slate-500 mt-0.5">{label}</p>
    </div>
  )
}

// ── Reasons tooltip / expand ──────────────────────────────────────────────────

function ReasonsCell({ reasons }: { reasons: string[] }) {
  const [open, setOpen] = useState(false)
  if (reasons.length === 0) return <span className="text-slate-600 text-xs">—</span>

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="text-xs text-blue-400 hover:text-blue-300 transition-colors text-left"
      >
        {reasons[0]}
        {reasons.length > 1 && (
          <span className="ml-1 text-slate-500">+{reasons.length - 1} more {open ? '▲' : '▼'}</span>
        )}
      </button>
      {open && reasons.length > 1 && (
        <ul className="mt-1.5 space-y-0.5">
          {reasons.slice(1).map((r, i) => (
            <li key={i} className="text-[11px] text-slate-500 pl-2 border-l border-slate-700">
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Category filter pills ─────────────────────────────────────────────────────

type Filter = 'ALL' | Classification

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'ALL',                label: 'All Fields' },
  { value: 'DIRECT_IDENTIFIER',  label: 'Direct ID' },
  { value: 'QUASI_IDENTIFIER',   label: 'Quasi ID' },
  { value: 'SENSITIVE_ATTRIBUTE',label: 'Sensitive' },
  { value: 'ACADEMIC_DATA',      label: 'Academic' },
  { value: 'PLACEMENT_DATA',     label: 'Placement' },
  { value: 'NON_SENSITIVE',      label: 'Non-Sensitive' },
]

// ── Main Dataset Scanner page ─────────────────────────────────────────────────

export default function DatasetScanner() {
  const [state, setState] = useState<ScanState>('idle')
  const [result, setResult] = useState<ScanResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('ALL')

  const runScan = useCallback(async () => {
    setState('loading')
    setError(null)
    setResult(null)

    try {
      // Fetch the built-in synthetic schema
      const schemaRes = await fetch(SCHEMA_URL)
      if (!schemaRes.ok) throw new Error(`Schema fetch failed: HTTP ${schemaRes.status}`)
      const schema: ScanRequest = await schemaRes.json()

      // Run the scan
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

  const filtered = result?.results.filter(
    r => filter === 'ALL' || r.classification === filter
  ) ?? []

  const sensitiveCount = result?.sensitive_count ?? 0
  const directCount = result?.results.filter(r => r.classification === 'DIRECT_IDENTIFIER').length ?? 0
  const quasiCount  = result?.results.filter(r => r.classification === 'QUASI_IDENTIFIER').length ?? 0

  return (
    <main className="flex-1 overflow-y-auto px-8 py-8">
      {/* Header */}
      <div className="mb-6 animate-fade-in-up opacity-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Phase 2 · Live
          </span>
          <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20">
            🔬 Synthetic Data Only
          </span>
        </div>
        <h1 className="text-2xl font-bold text-white">Dataset Scanner</h1>
        <p className="mt-1 text-sm text-slate-400">
          Scan dataset schemas for sensitive and PII fields using the Automated Detection Engine.
          Results call <code className="font-mono text-blue-400">POST /scan</code> — not demo data.
        </p>
      </div>

      {/* Scan controls */}
      <div className="card p-5 mb-6 animate-fade-in-up opacity-0 animate-delay-100">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-semibold text-white mb-0.5">University Synthetic Demo Schema</p>
            <p className="text-xs text-slate-500">
              14 fields · Built-in synthetic dataset · No real personal data
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
                Scanning…
              </>
            ) : (
              <>🔍 SCAN DATASET</>
            )}
          </button>
        </div>

        {/* What the scanner does */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { icon: '🔤', label: 'Field-name matching', color: 'text-blue-400' },
            { icon: '🔎', label: 'Value-pattern detection', color: 'text-purple-400' },
            { icon: '📐', label: 'Data-type analysis', color: 'text-cyan-400' },
            { icon: '🏷️', label: 'Semantic classification', color: 'text-emerald-400' },
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
        <div className="animate-fade-in-up opacity-0">
          {/* Summary stats */}
          <p className="section-title mb-3">Scan Summary · {result.dataset_name}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
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
          </div>

          {/* Filter pills */}
          <div className="flex flex-wrap gap-2 mb-4">
            {FILTERS.map(f => {
              const count = f.value === 'ALL'
                ? result.results.length
                : result.results.filter(r => r.classification === f.value).length
              return (
                <button
                  key={f.value}
                  onClick={() => setFilter(f.value)}
                  className={`badge border transition-all ${
                    filter === f.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-slate-700/40 text-slate-400 border-slate-600/50 hover:border-slate-500'
                  }`}
                >
                  {f.label}
                  <span className={`ml-1 text-[10px] ${filter === f.value ? 'text-blue-200' : 'text-slate-600'}`}>
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Results table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[rgb(var(--border-col))] bg-white/2">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Field</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Classification</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Confidence</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Signals</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Detection Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, idx) => (
                    <tr
                      key={r.field}
                      className={`border-b border-[rgb(var(--border-col))]/50 transition-colors hover:bg-white/2
                        ${idx % 2 === 0 ? '' : 'bg-white/1'}`}
                    >
                      <td className="px-4 py-3">
                        <code className="font-mono text-xs text-slate-300 bg-slate-700/40 px-1.5 py-0.5 rounded">
                          {r.field}
                        </code>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-500">{r.data_type}</span>
                      </td>
                      <td className="px-4 py-3">
                        <ClassificationBadge cls={r.classification} />
                      </td>
                      <td className="px-4 py-3">
                        <ConfidenceBar score={r.confidence} band={r.confidence_band} />
                      </td>
                      <td className="px-4 py-3">
                        <SignalDots field={r} />
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        <ReasonsCell reasons={r.reasons} />
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-600 text-sm">
                        No fields match the selected filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Scan metadata */}
          <p className="text-[11px] text-slate-600 mt-3">
            Scan ID: {result.scan_id} · {result.fields_scanned} fields processed · Results persisted to SQLite
          </p>
        </div>
      )}

      {/* Idle state hint */}
      {state === 'idle' && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[rgb(var(--border-col))] bg-[rgb(var(--bg-card))]/30 py-20 text-center">
          <div className="text-5xl mb-4 opacity-40">🔍</div>
          <p className="text-slate-400 font-medium">Ready to scan</p>
          <p className="text-slate-600 text-sm mt-1">
            Click <strong className="text-slate-400">SCAN DATASET</strong> to detect sensitive fields
          </p>
        </div>
      )}
    </main>
  )
}
