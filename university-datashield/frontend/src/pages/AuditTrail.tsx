import React, { useEffect, useState } from 'react'
import {
  Shield,
  RefreshCw,
  Search,
  Filter,
  FileText,
  Hash,
  EyeOff,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { AUDIT_URL, AUDIT_INTEGRITY_URL } from '../config'
import type { AuditEventRecord, AuditIntegrityResponse, AuditAction } from '../types'

export const AuditTrail: React.FC = () => {
  const [events, setEvents] = useState<AuditEventRecord[]>([])
  const [integrity, setIntegrity] = useState<AuditIntegrityResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [filterAction, setFilterAction] = useState<string>('')
  const [filterRole, setFilterRole] = useState<string>('')
  const [filterResult, setFilterResult] = useState<string>('')
  const [filterDataset, setFilterDataset] = useState<string>('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const fetchEvents = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (filterAction) params.append('action', filterAction)
      if (filterRole) params.append('actor_role', filterRole)
      if (filterResult) params.append('result', filterResult)
      if (filterDataset) params.append('dataset', filterDataset)
      params.append('limit', '150')

      const res = await fetch(`${AUDIT_URL}?${params.toString()}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data: AuditEventRecord[] = await res.json()
      setEvents(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load audit trail')
    } finally {
      setLoading(false)
    }
  }

  const checkIntegrity = async () => {
    setVerifying(true)
    try {
      const res = await fetch(AUDIT_INTEGRITY_URL)
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data: AuditIntegrityResponse = await res.json()
      setIntegrity(data)
    } catch (err: any) {
      setIntegrity({
        status: 'COMPROMISED',
        events_checked: 0,
        details: err.message || 'Failed to contact integrity verification service',
      })
    } finally {
      setVerifying(false)
    }
  }

  useEffect(() => {
    fetchEvents()
    checkIntegrity()
  }, [filterAction, filterRole, filterResult])

  const getActionBadge = (action: AuditAction) => {
    switch (action) {
      case 'ACCESS_DENIAL':
        return 'bg-red-500/20 text-red-400 border-red-500/40'
      case 'PUBLICATION':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
      case 'PUBLICATION_CHECK':
        return 'bg-sky-500/20 text-sky-400 border-sky-500/40'
      case 'POLICY_APPROVED':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/40'
      case 'POLICY_REJECTED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40'
      case 'POLICY_ROLLBACK':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40'
      case 'POLICY_CHANGE_PROPOSED':
        return 'bg-indigo-500/20 text-indigo-400 border-indigo-500/40'
      case 'POLICY_VALIDATION':
        return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40'
      default:
        return 'bg-slate-700/40 text-slate-300 border-slate-600/50'
    }
  }

  const getResultBadge = (result: string) => {
    const upper = result.toUpperCase()
    if (upper === 'ALLOW' || upper === 'PASS' || upper === 'APPROVED' || upper.includes('SCANNED')) {
      return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    }
    if (upper === 'BLOCK' || upper === 'FAIL' || upper === 'REJECTED' || upper === 'UNAUTHORIZED') {
      return 'bg-rose-500/15 text-rose-400 border-rose-500/30'
    }
    return 'bg-amber-500/15 text-amber-400 border-amber-500/30'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Immutable Audit Trail</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              Phase 6
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Tamper-evident governance ledger backed by SHA-256 hash chaining. Complete metadata accountability with zero raw PII retention.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              fetchEvents()
              checkIntegrity()
            }}
            disabled={loading || verifying}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm border border-slate-700 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading || verifying ? 'animate-spin text-cyan-400' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Cryptographic Hash Chain Integrity Banner */}
      {integrity && (
        <div
          className={`p-4 rounded-xl border ${
            integrity.status === 'VALID'
              ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/30 border-rose-500/40 text-rose-300'
          }`}
        >
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div
                className={`p-2.5 rounded-lg ${
                  integrity.status === 'VALID' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                }`}
              >
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-white">Cryptographic Integrity Status:</span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-bold ${
                      integrity.status === 'VALID'
                        ? 'bg-emerald-500 text-slate-950'
                        : 'bg-rose-500 text-white animate-pulse'
                    }`}
                  >
                    {integrity.status}
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-0.5">{integrity.details}</p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono text-slate-400 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800">
              <div>
                Events Checked: <span className="text-white font-bold">{integrity.events_checked}</span>
              </div>
              {integrity.head_hash && (
                <div className="hidden md:block">
                  Head Hash: <span className="text-cyan-400">{integrity.head_hash.substring(0, 16)}...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Privacy Guarantee Card */}
      <div className="flex items-center gap-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-800 text-xs text-slate-400">
        <EyeOff className="w-4 h-4 text-cyan-400 shrink-0" />
        <div>
          <span className="font-semibold text-slate-200">Strict Privacy Enforcement: </span>
          All audit records contain metadata, field schema categorizations, and security decisions only. Raw personal values, emails, and phone numbers are excluded at the database level.
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 flex flex-wrap items-center gap-3 text-sm">
        <div className="flex items-center gap-2 text-slate-400">
          <Filter className="w-4 h-4" />
          <span className="font-medium">Filter By:</span>
        </div>

        {/* Action Filter */}
        <select
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-3 py-1.5 focus:border-cyan-500 focus:outline-none text-xs"
        >
          <option value="">All Actions</option>
          <option value="SCAN">SCAN</option>
          <option value="POLICY_VALIDATION">POLICY_VALIDATION</option>
          <option value="PUBLICATION_CHECK">PUBLICATION_CHECK</option>
          <option value="PUBLICATION">PUBLICATION</option>
          <option value="ACCESS_DENIAL">ACCESS_DENIAL</option>
          <option value="POLICY_CHANGE_PROPOSED">POLICY_CHANGE_PROPOSED</option>
          <option value="POLICY_APPROVED">POLICY_APPROVED</option>
          <option value="POLICY_REJECTED">POLICY_REJECTED</option>
          <option value="POLICY_ROLLBACK">POLICY_ROLLBACK</option>
        </select>

        {/* Role Filter */}
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-3 py-1.5 focus:border-cyan-500 focus:outline-none text-xs"
        >
          <option value="">All Roles</option>
          <option value="DATA_ENGINEER">DATA_ENGINEER</option>
          <option value="ANALYST">ANALYST</option>
          <option value="FACULTY">FACULTY</option>
          <option value="PLACEMENT_ADMIN">PLACEMENT_ADMIN</option>
          <option value="SECURITY_ADMIN">SECURITY_ADMIN</option>
        </select>

        {/* Result Filter */}
        <select
          value={filterResult}
          onChange={(e) => setFilterResult(e.target.value)}
          className="bg-slate-950 border border-slate-700 text-slate-200 rounded-lg px-3 py-1.5 focus:border-cyan-500 focus:outline-none text-xs"
        >
          <option value="">All Results</option>
          <option value="ALLOW">ALLOW</option>
          <option value="BLOCK">BLOCK</option>
          <option value="PASS">PASS</option>
          <option value="FAIL">FAIL</option>
          <option value="REVIEW">REVIEW</option>
          <option value="APPROVED">APPROVED</option>
          <option value="REJECTED">REJECTED</option>
          <option value="PENDING">PENDING</option>
        </select>

        {/* Dataset Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search dataset name..."
            value={filterDataset}
            onChange={(e) => setFilterDataset(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchEvents()}
            className="w-full bg-slate-950 border border-slate-700 text-slate-200 rounded-lg pl-8 pr-3 py-1.5 focus:border-cyan-500 focus:outline-none text-xs"
          />
        </div>

        {(filterAction || filterRole || filterResult || filterDataset) && (
          <button
            onClick={() => {
              setFilterAction('')
              setFilterRole('')
              setFilterResult('')
              setFilterDataset('')
            }}
            className="text-xs text-cyan-400 hover:text-cyan-300 underline"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Audit Log Stream */}
      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-500/40 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800">
          <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin text-cyan-400" />
          Loading audit events...
        </div>
      ) : events.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800">
          <FileText className="w-8 h-8 mx-auto mb-2 text-slate-600" />
          No audit records matched your query filters.
        </div>
      ) : (
        <div className="bg-slate-900/80 rounded-xl border border-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4">Timestamp</th>
                  <th className="py-3.5 px-4">Actor</th>
                  <th className="py-3.5 px-4">Action</th>
                  <th className="py-3.5 px-4">Dataset / Field</th>
                  <th className="py-3.5 px-4">Result</th>
                  <th className="py-3.5 px-4">Policy Ver</th>
                  <th className="py-3.5 px-4">Explainable Rationale</th>
                  <th className="py-3.5 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {events.map((ev) => {
                  const isExpanded = expandedId === ev.id
                  return (
                    <React.Fragment key={ev.id}>
                      <tr className="hover:bg-slate-800/40 transition">
                        <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                          {new Date(ev.timestamp).toLocaleTimeString()}
                          <div className="text-[10px] text-slate-500">
                            {new Date(ev.timestamp).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="font-semibold text-slate-200 block">{ev.actor_role}</span>
                          <span className="text-[10px] font-mono text-slate-500">{ev.actor_id}</span>
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${getActionBadge(
                              ev.action
                            )}`}
                          >
                            {ev.action}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-slate-300 text-xs block">
                            {ev.dataset || '—'}
                          </span>
                          {ev.field_name && (
                            <span className="text-[10px] text-cyan-400 font-mono">
                              field: {ev.field_name}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${getResultBadge(
                              ev.result
                            )}`}
                          >
                            {ev.result}
                          </span>
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="font-mono px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300 text-[11px] border border-slate-700">
                            {ev.policy_version || 'v1.0'}
                          </span>
                        </td>
                        <td className="py-3 px-4 max-w-xs truncate text-slate-300" title={ev.reason || ''}>
                          {ev.reason || '—'}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : ev.id)}
                            className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition"
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded View for Cryptographic Chain & Metadata */}
                      {isExpanded && (
                        <tr className="bg-slate-950/80 border-b border-slate-800">
                          <td colSpan={8} className="p-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                              <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                                <div className="text-slate-400 font-semibold mb-1 flex items-center gap-1.5">
                                  <Hash className="w-3.5 h-3.5 text-cyan-400" />
                                  Cryptographic Hash Chaining:
                                </div>
                                <div className="space-y-1 text-[11px]">
                                  <div>
                                    <span className="text-slate-500">Event Hash:</span>{' '}
                                    <span className="text-cyan-300 break-all">{ev.event_hash}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500">Prev Hash: </span>{' '}
                                    <span className="text-slate-400 break-all">{ev.previous_hash}</span>
                                  </div>
                                  {ev.change_id && (
                                    <div>
                                      <span className="text-slate-500">Change ID: </span>{' '}
                                      <span className="text-amber-400">{ev.change_id}</span>
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                                <div className="text-slate-400 font-semibold mb-1 flex items-center gap-1.5">
                                  <FileText className="w-3.5 h-3.5 text-emerald-400" />
                                  Metadata Payload (Privacy-Safe):
                                </div>
                                <pre className="text-[11px] text-slate-300 overflow-x-auto max-h-24 bg-slate-950 p-2 rounded border border-slate-800">
                                  {ev.metadata_json && Object.keys(ev.metadata_json).length > 0
                                    ? JSON.stringify(ev.metadata_json, null, 2)
                                    : '// No additional metadata recorded'}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
export default AuditTrail
