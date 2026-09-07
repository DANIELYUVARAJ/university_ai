import { useState, useEffect } from 'react'
import { ROLES_URL } from '../config'
import type { RoleDetail, DemoRole } from '../types'

export default function AccessRoles() {
  const [roles, setRoles] = useState<RoleDetail[]>([])
  const [selectedRoleName, setSelectedRoleName] = useState<DemoRole>('ANALYST')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load active demo role from localStorage or default to ANALYST
  useEffect(() => {
    const saved = localStorage.getItem('datashield_current_role') as DemoRole | null
    if (saved) setSelectedRoleName(saved)
  }, [])

  const fetchRoles = async () => {
    try {
      setLoading(true)
      const res = await fetch(ROLES_URL)
      if (!res.ok) throw new Error(`Failed to load roles: ${res.status}`)
      const data: RoleDetail[] = await res.json()
      setRoles(data)
    } catch (err: any) {
      setError(err.message || 'Error fetching roles')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRoles()
  }, [])

  const handleRoleSelect = (role: DemoRole) => {
    setSelectedRoleName(role)
    localStorage.setItem('datashield_current_role', role)
  }

  const activeRole = roles.find((r) => r.role === selectedRoleName) || roles[0]

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="inline-block animate-spin text-3xl">👥</div>
          <div className="text-lg font-medium text-slate-200">Loading Role-Based Access Control...</div>
          <p className="text-sm text-slate-500">Retrieving institutional role-policy permissions matrix.</p>
        </div>
      </div>
    )
  }

  if (error || !activeRole) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center">
        <div className="card p-8 max-w-md text-center space-y-4 border-red-500/30 bg-red-500/5">
          <div className="text-3xl">⚠️</div>
          <h2 className="text-lg font-bold text-red-400">Failed to Load Roles</h2>
          <p className="text-sm text-slate-400">{error || 'Unknown error occurred'}</p>
          <button onClick={fetchRoles} className="btn btn-primary px-4 py-2 text-sm mx-auto">
            Retry
          </button>
        </div>
      </div>
    )
  }

  const permissions = activeRole.permissions

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Role-Based Access Control (RBAC)
            </h1>
            <span className="badge bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 text-xs font-semibold">
              Phase 5 Active
            </span>
            <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-semibold">
              Simulated Auth
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Simulated institutional role access policies and analytical publication authority.
          </p>
        </div>

        {/* Current Role Selector Dropdown */}
        <div className="flex items-center gap-3 bg-slate-900/90 p-2 rounded-xl border border-slate-800">
          <span className="text-xs text-slate-400 font-medium pl-2">Current Active Role:</span>
          <select
            id="role-selector"
            value={selectedRoleName}
            onChange={(e) => handleRoleSelect(e.target.value as DemoRole)}
            className="bg-slate-950 border border-indigo-500/40 text-indigo-300 font-bold text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-400"
          >
            {roles.map((r) => (
              <option key={r.role} value={r.role}>
                {r.title} ({r.role})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Selected Role Capability Card ───────────────────────────── */}
      <div className="card p-6 bg-gradient-to-r from-slate-900 via-slate-900/95 to-indigo-950/30 border-indigo-900/40 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-2xl">👤</span>
              <div>
                <h2 className="text-lg font-bold text-white">{activeRole.title}</h2>
                <p className="text-xs text-slate-400 font-mono">{activeRole.role}</p>
              </div>
            </div>
            <p className="text-xs text-slate-300 mt-2 max-w-xl">{activeRole.description}</p>
          </div>

          <div className="flex items-center gap-3">
            {activeRole.can_publish ? (
              <span className="badge bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-xs py-1 px-3 font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                Publication Authorized
              </span>
            ) : (
              <span className="badge bg-red-500/15 text-red-400 border border-red-500/30 text-xs py-1 px-3 font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-400" />
                Publication Restricted
              </span>
            )}
          </div>
        </div>

        {/* Action Capabilities Checklist */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          {/* View Schema */}
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-center justify-between">
            <span className="text-slate-300 font-medium">View Dataset Schemas</span>
            {permissions.VIEW_SCHEMA ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">✓ Allowed</span>
            ) : (
              <span className="text-red-400 font-bold flex items-center gap-1">✕ Denied</span>
            )}
          </div>

          {/* View Masked Data */}
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-center justify-between">
            <span className="text-slate-300 font-medium">View Masked &amp; Protected Data</span>
            {permissions.VIEW_MASKED_DATA ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">✓ Allowed</span>
            ) : (
              <span className="text-red-400 font-bold flex items-center gap-1">✕ Denied</span>
            )}
          </div>

          {/* Validate */}
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-center justify-between">
            <span className="text-slate-300 font-medium">Validate Masking Policies</span>
            {permissions.VALIDATE ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">✓ Allowed</span>
            ) : (
              <span className="text-red-400 font-bold flex items-center gap-1">✕ Denied</span>
            )}
          </div>

          {/* Publish */}
          <div className={`p-3 rounded-lg border flex items-center justify-between ${
            permissions.PUBLISH
              ? 'bg-emerald-950/20 border-emerald-900/30'
              : 'bg-red-950/20 border-red-900/30'
          }`}>
            <span className="text-slate-200 font-medium">Publish Compliant Datasets</span>
            {permissions.PUBLISH ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">✓ Authorized</span>
            ) : (
              <span className="text-red-400 font-bold flex items-center gap-1">✕ Blocked</span>
            )}
          </div>

          {/* Manage Policies */}
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-center justify-between">
            <span className="text-slate-300 font-medium">Manage Masking Policies</span>
            {permissions.MANAGE_POLICIES ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">✓ Admin Only</span>
            ) : (
              <span className="text-slate-500 font-bold flex items-center gap-1">✕ Denied</span>
            )}
          </div>

          {/* View Raw Sensitive Data */}
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800/80 flex items-center justify-between">
            <span className="text-slate-300 font-medium">Access Raw PII / Sensitive Data</span>
            {permissions.VIEW_RAW_SENSITIVE_DATA === 'CONTROLLED' ? (
              <span className="badge bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-bold">
                Controlled Audit
              </span>
            ) : (
              <span className="text-red-400 font-bold flex items-center gap-1">✕ Zero Access</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Complete Comparative Permission Matrix ─────────────────── */}
      <div className="card p-6 space-y-4">
        <div>
          <h3 className="text-base font-bold text-white">Institutional Role-Permission Matrix</h3>
          <p className="text-xs text-slate-400">
            Comparative view of access control across all 5 configured roles.
          </p>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4 font-semibold">Institutional Role</th>
                <th className="py-3 px-3 font-semibold text-center">View Schema</th>
                <th className="py-3 px-3 font-semibold text-center">View Masked</th>
                <th className="py-3 px-3 font-semibold text-center">View Raw PII</th>
                <th className="py-3 px-3 font-semibold text-center">Validate</th>
                <th className="py-3 px-3 font-semibold text-center">Publish Gate</th>
                <th className="py-3 px-3 font-semibold text-center">Manage Policies</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/30">
              {roles.map((r) => {
                const isCurrent = r.role === selectedRoleName
                return (
                  <tr
                    key={r.role}
                    onClick={() => handleRoleSelect(r.role)}
                    className={`cursor-pointer transition-colors ${
                      isCurrent
                        ? 'bg-indigo-950/40 border-l-4 border-indigo-500'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="py-3 px-4 font-medium">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-200">{r.title}</span>
                        {isCurrent && (
                          <span className="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-[9px] font-bold">
                            CURRENT
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">{r.role}</div>
                    </td>

                    {/* View Schema */}
                    <td className="py-3 px-3 text-center">
                      <span className="text-emerald-400 font-bold">✓ YES</span>
                    </td>

                    {/* View Masked */}
                    <td className="py-3 px-3 text-center">
                      <span className="text-emerald-400 font-bold">✓ YES</span>
                    </td>

                    {/* View Raw PII */}
                    <td className="py-3 px-3 text-center">
                      {r.permissions.VIEW_RAW_SENSITIVE_DATA === 'CONTROLLED' ? (
                        <span className="badge bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px]">
                          CONTROLLED
                        </span>
                      ) : (
                        <span className="text-slate-500 font-semibold">✕ NO</span>
                      )}
                    </td>

                    {/* Validate */}
                    <td className="py-3 px-3 text-center">
                      <span className="text-emerald-400 font-bold">✓ YES</span>
                    </td>

                    {/* Publish */}
                    <td className="py-3 px-3 text-center">
                      {r.permissions.PUBLISH ? (
                        <span className="badge bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">
                          ✓ YES
                        </span>
                      ) : r.role === 'PLACEMENT_ADMIN' ? (
                        <span className="badge bg-amber-500/15 text-amber-400 border border-amber-500/30 text-[10px]">
                          LIMITED
                        </span>
                      ) : (
                        <span className="text-slate-500 font-semibold">✕ NO</span>
                      )}
                    </td>

                    {/* Manage Policies */}
                    <td className="py-3 px-3 text-center">
                      {r.permissions.MANAGE_POLICIES ? (
                        <span className="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-bold">
                          ✓ YES
                        </span>
                      ) : (
                        <span className="text-slate-500 font-semibold">✕ NO</span>
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
