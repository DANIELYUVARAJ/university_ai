import { useState, useEffect } from 'react'
import { EVALUATE_URL } from '../config'
import type { EvaluationResponse, FieldComparison, Classification } from '../types'
import { ClassificationBadge, ConfidenceBar } from '../components/ScanResultBadges'

type FilterTab = 'all' | 'baseline_errors' | 'datashield_errors' | 'correct'

export default function Metrics() {
  const [data, setData] = useState<EvaluationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [evaluating, setEvaluating] = useState(false)

  const fetchEvaluation = async () => {
    try {
      setEvaluating(true)
      setError(null)
      const res = await fetch(EVALUATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(null),
      })
      if (!res.ok) {
        throw new Error(`Evaluation failed with status ${res.status}`)
      }
      const json: EvaluationResponse = await res.json()
      setData(json)
    } catch (err: any) {
      setError(err.message || 'Failed to load evaluation metrics')
    } finally {
      setLoading(false)
      setEvaluating(false)
    }
  };

  useEffect(() => {
    fetchEvaluation()
  }, [])

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="inline-block animate-spin text-3xl">⚙️</div>
          <div className="text-lg font-medium text-slate-200">Running Benchmark Evaluation...</div>
          <p className="text-sm text-slate-500 max-w-sm">
            Evaluating Simple Keyword Baseline vs Multi-Signal DataShield against synthetic ground truth.
          </p>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center">
        <div className="card p-8 max-w-md text-center space-y-4 border-red-500/30 bg-red-500/5">
          <div className="text-3xl">⚠️</div>
          <h2 className="text-lg font-bold text-red-400">Failed to Load Metrics</h2>
          <p className="text-sm text-slate-400">{error || 'Unknown error occurred'}</p>
          <button
            onClick={fetchEvaluation}
            className="btn btn-primary px-4 py-2 text-sm mx-auto"
          >
            Retry Benchmark
          </button>
        </div>
      </div>
    )
  }

  const { baseline, datashield, field_comparisons, total_fields } = data

  // Filter comparison rows based on activeTab and searchTerm
  const filteredRows = field_comparisons.filter((row: FieldComparison) => {
    // Search filter
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase()
      const matchName = row.field.toLowerCase().includes(q)
      const matchClass = (row.ground_truth_classification || '').toLowerCase().includes(q)
      if (!matchName && !matchClass) return false
    }

    if (activeTab === 'baseline_errors') return row.baseline_error
    if (activeTab === 'datashield_errors') return row.datashield_error
    if (activeTab === 'correct') return !row.baseline_error && !row.datashield_error
    return true
  })

  // Counts for tabs
  const baselineErrorCount = field_comparisons.filter((r) => r.baseline_error).length
  const datashieldErrorCount = field_comparisons.filter((r) => r.datashield_error).length
  const bothCorrectCount = field_comparisons.filter((r) => !r.baseline_error && !r.datashield_error).length

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Evaluation &amp; Baseline Benchmark
            </h1>
            <span className="badge bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 text-xs font-semibold">
              Phase 3 Live
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Empirical comparison of Keyword-Only Baseline vs Multi-Signal DataShield against {total_fields} synthetic ground-truth fields.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            id="run-evaluate-btn"
            onClick={fetchEvaluation}
            disabled={evaluating}
            className="btn bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-4 py-2 rounded-lg flex items-center gap-2 shadow-lg shadow-indigo-900/30 transition-all disabled:opacity-50"
          >
            <span>{evaluating ? '🔄 Running...' : '⚡ Re-run Evaluation'}</span>
          </button>
        </div>
      </div>

      {/* ── High-Level Performance Comparison KPI Cards ─────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Precision Card */}
        <div className="card p-5 space-y-3 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Precision</span>
            <span className={`badge text-[10px] font-bold ${
              datashield.precision >= baseline.precision
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-700/50 text-slate-400'
            }`}>
              +{((datashield.precision - baseline.precision) * 100).toFixed(1)}% Gain
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <div>
              <div className="text-2xl font-bold text-emerald-400">
                {(datashield.precision * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-400">DataShield Engine</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-slate-400">
                {(baseline.precision * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-500">Keyword Baseline</div>
            </div>
          </div>
        </div>

        {/* F1 Score Card */}
        <div className="card p-5 space-y-3 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">F1 Score</span>
            <span className="badge text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
              +{((datashield.f1 - baseline.f1) * 100).toFixed(1)}% Gain
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <div>
              <div className="text-2xl font-bold text-indigo-400">
                {(datashield.f1 * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-400">DataShield Engine</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-slate-400">
                {(baseline.f1 * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-500">Keyword Baseline</div>
            </div>
          </div>
        </div>

        {/* False Positives Card */}
        <div className="card p-5 space-y-3 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">False Positives</span>
            <span className="badge text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              {baseline.false_positives - datashield.false_positives} Traps Avoided
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <div>
              <div className="text-2xl font-bold text-emerald-400">
                {datashield.false_positives}
              </div>
              <div className="text-[11px] text-slate-400">DataShield (Zero Noise)</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-red-400">
                {baseline.false_positives}
              </div>
              <div className="text-[11px] text-slate-500">Baseline Traps</div>
            </div>
          </div>
        </div>

        {/* Accuracy Card */}
        <div className="card p-5 space-y-3 bg-gradient-to-br from-slate-900 to-slate-800/80 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Accuracy</span>
            <span className="badge text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/30">
              +{((datashield.accuracy - baseline.accuracy) * 100).toFixed(1)}% Gain
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <div>
              <div className="text-2xl font-bold text-purple-400">
                {(datashield.accuracy * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-400">DataShield Engine</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-slate-400">
                {(baseline.accuracy * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-500">Keyword Baseline</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 10: Comparison Visual Bars & Detailed Model Cards ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Visual Benchmark Comparison Bars */}
        <div className="lg:col-span-7 card p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white">Comparative Benchmark</h2>
              <p className="text-xs text-slate-400">Side-by-side metric distribution across validation fields</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-medium">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-slate-600 inline-block" />
                <span className="text-slate-400">Baseline</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-indigo-500 inline-block" />
                <span className="text-indigo-400 font-semibold">DataShield</span>
              </div>
            </div>
          </div>

          <div className="space-y-5">
            {/* Precision Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-300">Precision</span>
                <span className="text-slate-400 font-mono">
                  {(baseline.precision * 100).toFixed(1)}% vs <strong className="text-indigo-400 font-bold">{(datashield.precision * 100).toFixed(1)}%</strong>
                </span>
              </div>
              <div className="space-y-1">
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-slate-600 rounded-full transition-all duration-500"
                    style={{ width: `${baseline.precision * 100}%` }}
                  />
                </div>
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{ width: `${datashield.precision * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {/* F1 Score Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-300">F1 Score</span>
                <span className="text-slate-400 font-mono">
                  {(baseline.f1 * 100).toFixed(1)}% vs <strong className="text-indigo-400 font-bold">{(datashield.f1 * 100).toFixed(1)}%</strong>
                </span>
              </div>
              <div className="space-y-1">
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-slate-600 rounded-full transition-all duration-500"
                    style={{ width: `${baseline.f1 * 100}%` }}
                  />
                </div>
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{ width: `${datashield.f1 * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Recall Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-300">Recall</span>
                <span className="text-slate-400 font-mono">
                  {(baseline.recall * 100).toFixed(1)}% vs <strong className="text-indigo-400 font-bold">{(datashield.recall * 100).toFixed(1)}%</strong>
                </span>
              </div>
              <div className="space-y-1">
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-slate-600 rounded-full transition-all duration-500"
                    style={{ width: `${baseline.recall * 100}%` }}
                  />
                </div>
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{ width: `${datashield.recall * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Accuracy Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-300">Accuracy</span>
                <span className="text-slate-400 font-mono">
                  {(baseline.accuracy * 100).toFixed(1)}% vs <strong className="text-indigo-400 font-bold">{(datashield.accuracy * 100).toFixed(1)}%</strong>
                </span>
              </div>
              <div className="space-y-1">
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-slate-600 rounded-full transition-all duration-500"
                    style={{ width: `${baseline.accuracy * 100}%` }}
                  />
                </div>
                <div className="h-2.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{ width: `${datashield.accuracy * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* ASCII / Monospace representation requested in prompt */}
          <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800/80 font-mono text-xs text-slate-300 space-y-1">
            <div className="text-slate-500 text-[10px] uppercase font-bold tracking-widest pb-1 border-b border-slate-800">
              Normalized Detection Quality Comparison
            </div>
            <div className="flex justify-between items-center pt-1">
              <span className="text-slate-400 w-24">Baseline:</span>
              <span className="text-slate-500 font-bold flex-1 text-left">
                {'█'.repeat(Math.round(baseline.f1 * 20))}
                <span className="text-slate-800">{'░'.repeat(20 - Math.round(baseline.f1 * 20))}</span>
              </span>
              <span className="text-slate-400 w-16 text-right">{(baseline.f1 * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-indigo-400 font-semibold w-24">DataShield:</span>
              <span className="text-indigo-400 font-bold flex-1 text-left">
                {'█'.repeat(Math.round(datashield.f1 * 20))}
                <span className="text-slate-800">{'░'.repeat(20 - Math.round(datashield.f1 * 20))}</span>
              </span>
              <span className="text-indigo-300 font-bold w-16 text-right">{(datashield.f1 * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>

        {/* Side-by-Side Breakdown Tables */}
        <div className="lg:col-span-5 grid grid-cols-1 gap-4">
          {/* Baseline Summary Card */}
          <div className="card p-5 border-slate-800 bg-slate-900/60 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-slate-500" />
                <h3 className="text-sm font-bold text-slate-200">Baseline Detector</h3>
              </div>
              <span className="badge text-[10px] bg-slate-800 text-slate-400 border border-slate-700">
                Keyword Matching Only
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">Precision:</span>
                <span className="font-mono text-slate-200 font-semibold">{(baseline.precision * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">Recall:</span>
                <span className="font-mono text-slate-200 font-semibold">{(baseline.recall * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">F1 Score:</span>
                <span className="font-mono text-slate-200 font-semibold">{(baseline.f1 * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">Accuracy:</span>
                <span className="font-mono text-slate-200 font-semibold">{(baseline.accuracy * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-red-950/20 border border-red-900/30">
                <span className="text-red-400">False Positives:</span>
                <span className="font-mono text-red-400 font-bold">{baseline.false_positives}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-amber-950/20 border border-amber-900/30">
                <span className="text-amber-400">False Negatives:</span>
                <span className="font-mono text-amber-400 font-bold">{baseline.false_negatives}</span>
              </div>
            </div>
          </div>

          {/* DataShield Summary Card */}
          <div className="card p-5 border-indigo-900/40 bg-indigo-950/10 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-indigo-900/30">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
                <h3 className="text-sm font-bold text-indigo-300">DataShield Engine</h3>
              </div>
              <span className="badge text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                Multi-Signal (4 signals)
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">Precision:</span>
                <span className="font-mono text-emerald-400 font-bold">{(datashield.precision * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">Recall:</span>
                <span className="font-mono text-indigo-300 font-semibold">{(datashield.recall * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">F1 Score:</span>
                <span className="font-mono text-indigo-300 font-bold">{(datashield.f1 * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60">
                <span className="text-slate-400">Accuracy:</span>
                <span className="font-mono text-purple-300 font-semibold">{(datashield.accuracy * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-emerald-950/20 border border-emerald-900/30">
                <span className="text-emerald-400 font-semibold">False Positives:</span>
                <span className="font-mono text-emerald-400 font-bold">{datashield.false_positives}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-amber-950/20 border border-amber-900/30">
                <span className="text-amber-400">False Negatives:</span>
                <span className="font-mono text-amber-400 font-bold">{datashield.false_negatives}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 11: Error Analysis Table & Inspector ────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>Error Analysis &amp; Field Inspector</span>
              <span className="badge text-[11px] bg-slate-800 text-slate-400 border border-slate-700">
                {filteredRows.length} of {total_fields} fields
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Inspect model decisions against ground truth labels and identify exact root causes.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Search field or class..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500 w-48"
            />
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto text-xs">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              activeTab === 'all'
                ? 'bg-slate-800 text-white font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All Fields ({total_fields})
          </button>
          <button
            onClick={() => setActiveTab('baseline_errors')}
            className={`px-3 py-1.5 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'baseline_errors'
                ? 'bg-red-500/20 text-red-300 font-semibold border border-red-500/30'
                : 'text-slate-400 hover:text-red-300'
            }`}
          >
            <span>Baseline Errors</span>
            <span className="badge bg-red-500/30 text-red-300 text-[10px] px-1.5">
              {baselineErrorCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('datashield_errors')}
            className={`px-3 py-1.5 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'datashield_errors'
                ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30'
                : 'text-slate-400 hover:text-amber-300'
            }`}
          >
            <span>DataShield Misses</span>
            <span className="badge bg-amber-500/30 text-amber-300 text-[10px] px-1.5">
              {datashieldErrorCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('correct')}
            className={`px-3 py-1.5 rounded-md font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'correct'
                ? 'bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30'
                : 'text-slate-400 hover:text-emerald-300'
            }`}
          >
            <span>Both Correct</span>
            <span className="badge bg-emerald-500/30 text-emerald-300 text-[10px] px-1.5">
              {bothCorrectCount}
            </span>
          </button>
        </div>

        {/* Evaluation Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4 font-semibold">Field</th>
                <th className="py-3 px-3 font-semibold">Expected (Ground Truth)</th>
                <th className="py-3 px-3 font-semibold">Baseline Prediction</th>
                <th className="py-3 px-3 font-semibold">DataShield Detection</th>
                <th className="py-3 px-3 font-semibold">Comparison Result</th>
                <th className="py-3 px-4 font-semibold">Reason / Root Cause</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/30">
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500 italic">
                    No fields match the selected filter.
                  </td>
                </tr>
              ) : (
                filteredRows.map((row: FieldComparison) => {
                  // Determine overall outcome tag
                  let outcomeTag = (
                    <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Both Correct
                    </span>
                  )
                  if (!row.datashield_error && row.baseline_error) {
                    outcomeTag = (
                      <span className="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-bold">
                        ⭐ DataShield Superior
                      </span>
                    )
                  } else if (row.datashield_error && !row.baseline_error) {
                    outcomeTag = (
                      <span className="badge bg-amber-500/20 text-amber-300 border border-amber-500/40">
                        DataShield Miss
                      </span>
                    )
                  } else if (row.datashield_error && row.baseline_error) {
                    outcomeTag = (
                      <span className="badge bg-red-500/20 text-red-300 border border-red-500/40">
                        Both Failed
                      </span>
                    )
                  }

                  return (
                    <tr key={row.field} className="hover:bg-slate-800/40 transition-colors">
                      {/* Field name and type */}
                      <td className="py-3 px-4 font-mono font-medium text-slate-200">
                        <div>{row.field}</div>
                        <div className="text-[10px] text-slate-500 font-sans">{row.data_type}</div>
                      </td>

                      {/* Ground Truth */}
                      <td className="py-3 px-3">
                        <div className="flex flex-col items-start gap-1">
                          <span
                            className={`badge text-[10px] font-bold ${
                              row.ground_truth_sensitive
                                ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                                : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            }`}
                          >
                            {row.ground_truth_sensitive ? 'SENSITIVE' : 'NON-SENSITIVE'}
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {row.ground_truth_classification}
                          </span>
                        </div>
                      </td>

                      {/* Baseline */}
                      <td className="py-3 px-3">
                        <div className="flex flex-col items-start gap-1">
                          <span
                            className={`badge text-[10px] font-medium ${
                              row.baseline_prediction
                                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                : 'bg-slate-800 text-slate-400'
                            }`}
                          >
                            {row.baseline_prediction ? 'Flagged Sensitive' : 'Non-sensitive'}
                          </span>
                          {row.baseline_error && (
                            <span className="badge bg-red-950/40 text-red-400 border border-red-800/40 text-[9px] font-bold">
                              {row.baseline_error_type}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* DataShield */}
                      <td className="py-3 px-3">
                        <div className="flex flex-col items-start gap-1.5">
                          <div className="flex items-center gap-1.5">
                            <ClassificationBadge cls={row.datashield_classification as Classification} />
                            {row.datashield_error && (
                              <span className="badge bg-amber-950/40 text-amber-400 border border-amber-800/40 text-[9px] font-bold">
                                {row.datashield_error_type}
                              </span>
                            )}
                          </div>
                          <ConfidenceBar
                            score={row.datashield_confidence}
                            band={row.datashield_confidence_band}
                          />
                        </div>
                      </td>

                      {/* Comparison Result */}
                      <td className="py-3 px-3">{outcomeTag}</td>

                      {/* Reason / Root Cause */}
                      <td className="py-3 px-4 text-slate-400 text-[11px] max-w-xs">
                        {row.explanation}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
