import React from 'react'
import {
  ShieldCheck,
  Lock,
  Database,
  CheckCircle2,
  FileCode,
  Layers,
  Sparkles,
} from 'lucide-react'

export const PrivacyByDesign: React.FC = () => {
  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="border-b border-[rgb(var(--color-border))] pb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            <Lock className="h-7 w-7 text-cyan-400" />
            Privacy by Design &amp; Data Minimization
          </h1>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            Phase 8 Certified
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-400 max-w-3xl">
          University DataShield is architected from the ground up to never ingest, persist, or expose real personal student information.
        </p>
      </div>

      {/* Core Privacy Pillars */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 w-fit text-cyan-400">
            <Sparkles className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-white">100% Synthetic Data</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            All evaluation datasets, schema benchmarks, and test suites run entirely on mathematically generated synthetic personas. No real student, faculty, or institutional records are ever required.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3">
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 w-fit text-emerald-400">
            <Layers className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-white">Schema Metadata Only</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            The platform inspects structural column headers, data types, and pattern distributions. Governance workflows, change proposals, and version snapshots store field metadata rather than raw cell values.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-3">
          <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 w-fit text-purple-400">
            <Database className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-white">Immutable Hash Audit</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Every scan, validation check, publication gate decision, and rollback is recorded in an append-only SHA-256 cryptographic chain capturing decisions and reason codes, with zero raw personal identifiers.
          </p>
        </div>
      </div>

      {/* Database Verification Proof */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              Automated Database Inspection Verification
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Automated regression suites actively scan SQLite database tables to ensure zero PII leakage.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" />
            100% VERIFIED
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 text-[11px] uppercase font-bold text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Database Table</th>
                <th className="py-3 px-4">Monitored Columns</th>
                <th className="py-3 px-4">Storage Policy</th>
                <th className="py-3 px-4">Raw Data Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              <tr className="hover:bg-slate-800/30">
                <td className="py-3 px-4 font-mono font-bold text-cyan-300">audit_events</td>
                <td className="py-3 px-4 text-slate-400">dataset, field_name, result, reason, metadata_json</td>
                <td className="py-3 px-4">SHA-256 hashed decisions and metadata</td>
                <td className="py-3 px-4 text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Zero Raw PII
                </td>
              </tr>
              <tr className="hover:bg-slate-800/30">
                <td className="py-3 px-4 font-mono font-bold text-cyan-300">policy_change_requests</td>
                <td className="py-3 px-4 text-slate-400">reason, proposed_change_json, review_reason</td>
                <td className="py-3 px-4">Rule change targets &amp; protection actions</td>
                <td className="py-3 px-4 text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Zero Raw PII
                </td>
              </tr>
              <tr className="hover:bg-slate-800/30">
                <td className="py-3 px-4 font-mono font-bold text-cyan-300">policy_versions</td>
                <td className="py-3 px-4 text-slate-400">description, policy_snapshot</td>
                <td className="py-3 px-4">Classification defaults &amp; field overrides</td>
                <td className="py-3 px-4 text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Zero Raw PII
                </td>
              </tr>
              <tr className="hover:bg-slate-800/30">
                <td className="py-3 px-4 font-mono font-bold text-cyan-300">publication_attempts</td>
                <td className="py-3 px-4 text-slate-400">role, decision, status, reasons_json</td>
                <td className="py-3 px-4">Gate outcomes and policy compliance reasons</td>
                <td className="py-3 px-4 text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Zero Raw PII
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Architectural Guarantee Summary */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 border border-slate-800 flex items-start gap-4">
        <FileCode className="h-6 w-6 text-indigo-400 shrink-0 mt-1" />
        <div>
          <h4 className="text-sm font-bold text-white">Continuous Compliance via Automated Testing</h4>
          <p className="text-xs text-slate-300 mt-1 leading-relaxed">
            In our automated regression suite (<code className="text-cyan-300 font-mono">tests/test_phase8_integration.py</code> and <code className="text-cyan-300 font-mono">tests/test_security_validation.py</code>), every test run actively performs full-text regex scanning across all database columns to assert that no synthetic tokens (e.g. emails, phone numbers, student IDs) leak into stored records.
          </p>
        </div>
      </div>
    </div>
  )
}

export default PrivacyByDesign
