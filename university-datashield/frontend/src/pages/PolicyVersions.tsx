import React, { useEffect, useState } from 'react'
import {
  History,
  GitCompare,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Clock,
  User,
  X,
  RefreshCw,
} from 'lucide-react'
import {
  POLICY_VERSIONS_URL,
  POLICY_DIFF_URL,
  POLICY_ROLLBACK_URL,
} from '../config'
import type {
  PolicyVersionRecord,
  PolicyDiffResponse,
  RollbackResponse,
  DemoRole,
} from '../types'

interface PolicyVersionsProps {
  currentRole?: DemoRole
}

export const PolicyVersions: React.FC<PolicyVersionsProps> = ({
  currentRole = 'SECURITY_ADMIN',
}) => {
  const [versions, setVersions] = useState<PolicyVersionRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Diff state
  const [fromVer, setFromVer] = useState<string>('')
  const [toVer, setToVer] = useState<string>('')
  const [diffResult, setDiffResult] = useState<PolicyDiffResponse | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  // Rollback modal state
  const [rollbackTarget, setRollbackTarget] = useState<string | null>(null)
  const [rollbackReason, setRollbackReason] = useState('')
  const [rollbackExecuting, setRollbackExecuting] = useState(false)
  const [rollbackOutcome, setRollbackOutcome] = useState<RollbackResponse | null>(null)
  const [rollbackError, setRollbackError] = useState<string | null>(null)

  const isSecurityAdmin = currentRole === 'SECURITY_ADMIN'

  const fetchVersions = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(POLICY_VERSIONS_URL)
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data: PolicyVersionRecord[] = await res.json()
      setVersions(data)

      if (data.length >= 2) {
        setFromVer(data[0].version)
        setToVer(data[data.length - 1].version)
      } else if (data.length === 1) {
        setFromVer(data[0].version)
        setToVer(data[0].version)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch policy versions')
    } finally {
      setLoading(false)
    }
  }

  const runDiff = async (from: string, to: string) => {
    if (!from || !to) return
    setDiffLoading(true)
    try {
      const res = await fetch(`${POLICY_DIFF_URL}?from_version=${from}&to_version=${to}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data: PolicyDiffResponse = await res.json()
      setDiffResult(data)
    } catch (err: any) {
      console.error('Diff error:', err)
    } finally {
      setDiffLoading(false)
    }
  }

  useEffect(() => {
    fetchVersions()
  }, [])

  useEffect(() => {
    if (fromVer && toVer && fromVer !== toVer) {
      runDiff(fromVer, toVer)
    }
  }, [fromVer, toVer])

  const handleRollback = async () => {
    if (!rollbackTarget) return
    setRollbackExecuting(true)
    setRollbackError(null)
    try {
      const res = await fetch(POLICY_ROLLBACK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_version: rollbackTarget,
          actor_role: currentRole,
          actor_id: `${currentRole.toLowerCase()}-demo`,
          reason: rollbackReason.trim() || `Reverting policy to snapshot of ${rollbackTarget}`,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || `Rollback failed (HTTP ${res.status})`)
      }

      setRollbackOutcome(data)
      setRollbackTarget(null)
      setRollbackReason('')
      // Refresh version list
      fetchVersions()
    } catch (err: any) {
      setRollbackError(err.message || 'Failed to execute rollback')
    } finally {
      setRollbackExecuting(false)
    }
  }

  const activeVersion = versions.find((v) => v.active)

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Policy Versions & Rollback</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              Phase 6
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Immutable policy history, version diff inspection, and safe rollbacks with automatic post-rollback revalidation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-xs bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800 text-slate-300">
            Active Version:{' '}
            <span className="text-emerald-400 font-bold font-mono">
              {activeVersion ? activeVersion.version : 'Loading...'}
            </span>
          </div>
          <button
            onClick={fetchVersions}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm border border-slate-700 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Role Notice */}
      {!isSecurityAdmin && (
        <div className="p-3.5 bg-amber-950/30 border border-amber-500/30 rounded-xl text-xs text-amber-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            Current viewing role is <strong className="text-white">{currentRole}</strong>. Policy rollbacks and change approvals are strictly restricted to <strong>SECURITY_ADMIN</strong>.
          </span>
        </div>
      )}

      {/* Post-Rollback Outcome Alert */}
      {rollbackOutcome && (
        <div className="p-5 bg-emerald-950/40 border border-emerald-500/50 rounded-xl text-emerald-200 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold text-white">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              Rollback Successfully Executed & Revalidated
            </div>
            <button
              onClick={() => setRollbackOutcome(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Dismiss
            </button>
          </div>
          <p className="text-xs text-emerald-300">{rollbackOutcome.message}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono pt-2">
            <div className="bg-slate-900/80 p-2.5 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Active Version:</span>
              <span className="text-white font-bold">{rollbackOutcome.resulting_active_version}</span>
            </div>
            <div className="bg-slate-900/80 p-2.5 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Target Config:</span>
              <span className="text-cyan-400 font-bold">{rollbackOutcome.target_version}</span>
            </div>
            <div className="bg-slate-900/80 p-2.5 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Post-Validation:</span>
              <span className="text-emerald-400 font-bold">
                {rollbackOutcome.revalidation_status} (100% compliant)
              </span>
            </div>
            <div className="bg-slate-900/80 p-2.5 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Previous Version:</span>
              <span className="text-slate-400 font-bold">{rollbackOutcome.previous_version}</span>
            </div>
          </div>
        </div>
      )}

      {/* Rollback Error Alert */}
      {rollbackError && (
        <div className="p-4 bg-rose-950/40 border border-rose-500/40 rounded-xl text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{rollbackError}</span>
          </div>
          <button onClick={() => setRollbackError(null)} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Version Timeline */}
      <div className="bg-slate-900/80 rounded-xl border border-slate-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-bold text-white">Immutable Version Timeline</h2>
          </div>
          <span className="text-xs text-slate-400">Total Versions: {versions.length}</span>
        </div>

        {error && (
          <div className="p-4 bg-rose-950/40 border border-rose-500/40 rounded-xl text-rose-300 text-xs mb-4">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {versions.map((v) => {
            const isTarget = rollbackTarget === v.version
            return (
              <div
                key={v.id}
                className={`p-4 rounded-xl border transition ${
                  isTarget
                    ? 'border-amber-500 bg-amber-950/20'
                    : v.active
                    ? 'bg-emerald-950/20 border-emerald-500/50 shadow-sm shadow-emerald-950'
                    : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start sm:items-center gap-3">
                    <div
                      className={`p-2 rounded-lg font-mono text-sm font-bold ${
                        v.active
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : 'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}
                    >
                      {v.version}
                    </div>

                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-white text-sm">{v.description}</span>
                        {v.active && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500 text-slate-950">
                            CURRENTLY ACTIVE
                          </span>
                        )}
                        {!v.active && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                            {v.status}
                          </span>
                        )}
                        {v.change_id && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            {v.change_id}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-4 text-xs text-slate-400 mt-1 font-mono">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {new Date(v.created_at).toLocaleString()}
                        </span>
                        <span className="flex items-center gap-1">
                          <User className="w-3.5 h-3.5" />
                          {v.created_by}
                        </span>
                        {v.parent_version && <span>Parent: {v.parent_version}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 self-end sm:self-center">
                    {!v.active && (
                      <button
                        onClick={() => {
                          setRollbackTarget(v.version)
                          setRollbackReason(`Rollback active policy configuration to ${v.version}`)
                        }}
                        disabled={!isSecurityAdmin}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                          isSecurityAdmin
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
                            : 'bg-slate-800/40 text-slate-500 border border-slate-800 cursor-not-allowed'
                        }`}
                        title={isSecurityAdmin ? 'Rollback active policy to this version' : 'Requires SECURITY_ADMIN role'}
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        Rollback to this
                      </button>
                    )}
                  </div>
                </div>

                {/* Overrides quick preview */}
                <div className="mt-3 pt-3 border-t border-slate-800/60 flex flex-wrap gap-2 text-xs">
                  <span className="text-slate-500 text-[11px] self-center">Field Overrides:</span>
                  {Object.entries(v.policy_snapshot.field_overrides).map(([f, a]) => (
                    <span
                      key={f}
                      className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono"
                    >
                      <span className="text-slate-400">{f}:</span>{' '}
                      <span className="text-cyan-300 font-semibold">{a}</span>
                    </span>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Rollback Confirmation Modal */}
      {rollbackTarget && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-amber-500/50 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-amber-400">
              <div className="p-2.5 rounded-xl bg-amber-500/20 border border-amber-500/30">
                <RotateCcw className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Confirm Policy Rollback</h3>
                <span className="text-xs text-amber-300 font-semibold uppercase tracking-wider">
                  High-Impact Governance Action
                </span>
              </div>
            </div>

            <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Current Active Version:</span>
                <span className="text-white font-mono font-bold">{activeVersion?.version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Target Rollback Version:</span>
                <span className="text-cyan-400 font-mono font-bold">{rollbackTarget}</span>
              </div>
              <div className="pt-2 border-t border-slate-800 text-slate-300">
                ⚠️ <strong className="text-white">History Preservation:</strong> The existing version will remain in the permanent audit ledger. A new rollback version (e.g.{' '}
                <span className="font-mono text-cyan-300">v1.{versions.length}-rollback</span>) will be generated and verified automatically against the synthetic test dataset.
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Governance Reason for Rollback:
              </label>
              <textarea
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                rows={2}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
                placeholder="Document justification for returning to earlier policy..."
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setRollbackTarget(null)}
                disabled={rollbackExecuting}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition"
              >
                Cancel
              </button>
              <button
                onClick={handleRollback}
                disabled={rollbackExecuting}
                className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg text-xs font-bold transition shadow-md shadow-amber-500/20"
              >
                {rollbackExecuting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Revalidating & Rolling Back...
                  </>
                ) : (
                  <>
                    <RotateCcw className="w-3.5 h-3.5" />
                    Confirm Rollback
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Policy Comparison / Diff Viewer */}
      <div className="bg-slate-900/80 rounded-xl border border-slate-800 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <GitCompare className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-bold text-white">Policy Comparison & Diff</h2>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">From:</span>
              <select
                value={fromVer}
                onChange={(e) => setFromVer(e.target.value)}
                className="bg-slate-950 border border-slate-700 text-slate-200 rounded px-2 py-1 focus:border-cyan-500 focus:outline-none"
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    {v.version} {v.active ? '(Active)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <ArrowRight className="w-4 h-4 text-slate-500" />

            <div className="flex items-center gap-2">
              <span className="text-slate-400">To:</span>
              <select
                value={toVer}
                onChange={(e) => setToVer(e.target.value)}
                className="bg-slate-950 border border-slate-700 text-slate-200 rounded px-2 py-1 focus:border-cyan-500 focus:outline-none"
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    {v.version} {v.active ? '(Active)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => runDiff(fromVer, toVer)}
              disabled={diffLoading || !fromVer || !toVer}
              className="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded font-medium transition"
            >
              Compare
            </button>
          </div>
        </div>

        {diffResult && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-slate-800">
              <div>
                Comparing <strong className="text-cyan-400">{diffResult.from_version}</strong> →{' '}
                <strong className="text-cyan-400">{diffResult.to_version}</strong>
              </div>
              <div>
                Changes Detected:{' '}
                <span
                  className={`font-bold font-mono ${
                    diffResult.changes_count > 0 ? 'text-amber-400' : 'text-emerald-400'
                  }`}
                >
                  {diffResult.changes_count}
                </span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3">Rule / Field Target</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">{diffResult.from_version} Action</th>
                    <th className="py-2.5 px-3">{diffResult.to_version} Action</th>
                    <th className="py-2.5 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                  {diffResult.diffs.map((d, i) => (
                    <tr
                      key={i}
                      className={
                        d.changed
                          ? 'bg-amber-500/10 hover:bg-amber-500/15 transition'
                          : 'hover:bg-slate-800/30 transition'
                      }
                    >
                      <td className="py-2 px-3 font-semibold text-white">
                        {d.target}
                      </td>
                      <td className="py-2 px-3 text-slate-400 text-[11px]">
                        {d.is_field_override ? 'Field Override' : 'Category Default'}
                      </td>
                      <td className="py-2 px-3 text-slate-400">
                        {d.from_action || 'NONE'}
                      </td>
                      <td className="py-2 px-3">
                        <span className={d.changed ? 'text-amber-300 font-bold' : 'text-slate-300'}>
                          {d.to_action || 'NONE'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right">
                        {d.changed ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            MODIFIED
                          </span>
                        ) : (
                          <span className="text-slate-500 text-[10px]">unchanged</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
export default PolicyVersions
