import { NavLink } from 'react-router-dom'
import type { BackendStatus } from '../types'

interface NavItem {
  path: string
  label: string
  icon: string
  phase1Ready: boolean
}

const NAV_ITEMS: NavItem[] = [
  { path: '/',                  label: 'Dashboard',            icon: '◈', phase1Ready: true },
  { path: '/scanner',           label: 'Dataset Scanner',      icon: '⬡', phase1Ready: true },
  { path: '/pipeline-monitor',  label: 'Pipeline Monitor',     icon: '⚡', phase1Ready: true },
  { path: '/policy-validator',  label: 'Policy Validator',     icon: '📋', phase1Ready: true },
  { path: '/publication-gate',  label: 'Publication Gate',     icon: '🚦', phase1Ready: true },
  { path: '/access-roles',      label: 'Access Roles',         icon: '👥', phase1Ready: true },
  { path: '/audit-trail',       label: 'Audit Trail',          icon: '◎', phase1Ready: true },
  { path: '/policy-versions',   label: 'Policy Versions',      icon: '◫', phase1Ready: true },
  { path: '/change-review',     label: 'Change Review',        icon: '⚖', phase1Ready: true },
  { path: '/metrics',           label: 'Evaluation & Metrics', icon: '📊', phase1Ready: true },
  { path: '/security-validation', label: 'Security Validation', icon: '🛡️', phase1Ready: true },
  { path: '/privacy',           label: 'Privacy by Design',    icon: '🔐', phase1Ready: true },
]

interface SidebarProps {
  backendStatus: BackendStatus
}

export default function Sidebar({ backendStatus }: SidebarProps) {
  const statusColor =
    backendStatus === 'online'   ? 'bg-emerald-400' :
    backendStatus === 'offline'  ? 'bg-red-400'     :
                                   'bg-amber-400'

  const statusLabel =
    backendStatus === 'online'   ? 'API Connected' :
    backendStatus === 'offline'  ? 'API Offline'   :
                                   'Checking…'

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-[rgb(var(--color-border))] bg-[rgb(var(--color-bg-secondary))]">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-[rgb(var(--color-border))]">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 text-white text-lg font-bold shadow-lg">
          🛡
        </div>
        <div>
          <p className="text-sm font-bold text-white leading-tight">DataShield</p>
          <p className="text-[10px] text-slate-500 leading-tight">University Security Suite</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        <p className="section-title px-3 pb-2">Navigation</p>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item-active' : ''} group`
            }
          >
            <span className="text-base leading-none">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {!item.phase1Ready && (
              <span className="badge bg-slate-700/60 text-slate-500 text-[10px]">Soon</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer – live API status */}
      <div className="border-t border-[rgb(var(--color-border))] px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="relative flex h-2.5 w-2.5">
            {backendStatus === 'online' && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400/50" />
            )}
            <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${statusColor}`} />
          </div>
          <span className="text-xs text-slate-400">{statusLabel}</span>
        </div>
        <p className="mt-1 text-[10px] text-slate-600">Phase 11 · Production Hardened &amp; Security Gate Ready</p>
      </div>
    </aside>
  )
}
