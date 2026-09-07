import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import DatasetScanner from './pages/DatasetScanner'
import Metrics from './pages/Metrics'
import PolicyValidator from './pages/PolicyValidator'
import PublicationGate from './pages/PublicationGate'
import AccessRoles from './pages/AccessRoles'
import AuditTrail from './pages/AuditTrail'
import PolicyVersions from './pages/PolicyVersions'
import ChangeReview from './pages/ChangeReview'
import SecurityValidation from './pages/SecurityValidation'
import PrivacyByDesign from './pages/PrivacyByDesign'
import PlaceholderPage from './pages/PlaceholderPage'
import { useHealth } from './hooks/useHealth'
import type { DemoRole } from './types'

export default function App() {
  // Health check lives at the App level so Sidebar and Dashboard share the same state
  const { status } = useHealth()
  const [currentRole, setCurrentRole] = useState<DemoRole>('SECURITY_ADMIN')

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar navigation */}
        <Sidebar backendStatus={status} />

        {/* Header + page content */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top header bar */}
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-[rgb(var(--color-border))] bg-[rgb(var(--color-bg-secondary))]/80 backdrop-blur-sm px-8">
            <div>
              <h1 className="text-sm font-bold text-white">University DataShield</h1>
              <p className="text-[10px] text-slate-500">Sensitive Data Protection &amp; Analytics Publication Validator</p>
            </div>
            <div className="flex items-center gap-3">
              {/* Role Switcher */}
              <div className="flex items-center gap-1.5 bg-slate-900/90 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs">
                <span className="text-[10px] uppercase font-bold text-slate-400">Demo Role:</span>
                <select
                  value={currentRole}
                  onChange={(e) => setCurrentRole(e.target.value as DemoRole)}
                  className="bg-transparent text-cyan-300 font-semibold focus:outline-none cursor-pointer text-xs"
                >
                  <option value="SECURITY_ADMIN" className="bg-slate-900 text-white">SECURITY_ADMIN</option>
                  <option value="DATA_ENGINEER" className="bg-slate-900 text-white">DATA_ENGINEER</option>
                  <option value="ANALYST" className="bg-slate-900 text-white">ANALYST</option>
                  <option value="FACULTY" className="bg-slate-900 text-white">FACULTY</option>
                  <option value="PLACEMENT_ADMIN" className="bg-slate-900 text-white">PLACEMENT_ADMIN</option>
                </select>
              </div>

              <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs">
                🔬 Synthetic Data Only
              </span>
              <span className="badge bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-bold">
                Phase 8
              </span>
            </div>
          </header>

          {/* Page routes */}
          <main className="flex-1 overflow-y-auto p-6 md:p-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/scanner" element={<DatasetScanner />} />
              <Route
                path="/classification"
                element={
                  <PlaceholderPage
                    title="Field Classification"
                    description="Review automatic PII and FERPA field classifications, and apply manual overrides."
                    icon="🏷️"
                    phase="Phase 3"
                  />
                }
              />
              <Route path="/policy-validator" element={<PolicyValidator />} />
              <Route path="/publication-gate" element={<PublicationGate />} />
              <Route path="/access-roles" element={<AccessRoles />} />
              <Route path="/audit-trail" element={<AuditTrail />} />
              <Route path="/policy-versions" element={<PolicyVersions currentRole={currentRole} />} />
              <Route path="/change-review" element={<ChangeReview currentRole={currentRole} />} />
              <Route path="/metrics" element={<Metrics />} />
              <Route path="/security-validation" element={<SecurityValidation currentRole={currentRole} />} />
              <Route path="/privacy" element={<PrivacyByDesign />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
