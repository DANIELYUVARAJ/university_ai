import React, { useEffect, useState } from 'react'
import {
  FileCheck2,
  PlusCircle,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  User,
  Shield,
  ArrowRight,
  RefreshCw,
  X,
} from 'lucide-react'
import {
  POLICY_CHANGES_URL,
  POLICY_PROPOSE_URL,
  POLICY_APPROVE_URL,
  POLICY_REJECT_URL,
} from '../config'
import type {
  PolicyChangeRecord,
  ProtectionAction,
  DemoRole,
} from '../types'

interface ChangeReviewProps {
  currentRole?: DemoRole
}

export const ChangeReview: React.FC<ChangeReviewProps> = ({
  currentRole = 'DATA_ENGINEER',
}) => {
  const [changes, setChanges] = useState<PolicyChangeRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // Propose modal
  const [showProposeModal, setShowProposeModal] = useState(false)
  const [proposeTarget, setProposeTarget] = useState('phone')
  const [proposeIsField, setProposeIsField] = useState(true)
  const [proposeAction, setProposeAction] = useState<ProtectionAction>('GENERALIZE')
  const [proposeReason, setProposeReason] = useState('')
  const [submittingPropose, setSubmittingPropose] = useState(false)

  // Review modal
  const [reviewChangeId, setReviewChangeId] = useState<string | null>(null)
  const [reviewType, setReviewType] = useState<'APPROVE' | 'REJECT'>('APPROVE')
  const [reviewReason, setReviewReason] = useState('')
  const [submittingReview, setSubmittingReview] = useState(false)

  const isSecurityAdmin = currentRole === 'SECURITY_ADMIN'
  const currentActorId = `${currentRole.toLowerCase()}-demo`

  const fetchChanges = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(POLICY_CHANGES_URL)
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      const data: PolicyChangeRecord[] = await res.json()
      setChanges(data)
    } catch (err: any) {
      setError(err.message || 'Failed to fetch policy change requests')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchChanges()
  }, [])

  const handlePropose = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!proposeReason.trim()) {
      setError('A valid business justification reason is required for policy proposals.')
      return
    }

    setSubmittingPropose(true)
    setError(null)
    try {
      const res = await fetch(POLICY_PROPOSE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: proposeTarget,
          is_field_override: proposeIsField,
          proposed_action: proposeAction,
          reason: proposeReason.trim(),
          requested_by_role: currentRole,
          requested_by_actor: currentActorId,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || `Propose failed (HTTP ${res.status})`)
      }

      setActionSuccess(`Change request ${data.id} proposed successfully in PENDING status.`)
      setShowProposeModal(false)
      setProposeReason('')
      fetchChanges()
    } catch (err: any) {
      setError(err.message || 'Failed to propose change request')
    } finally {
      setSubmittingPropose(false)
    }
  }

  const handleExecuteReview = async () => {
    if (!reviewChangeId) return
    setSubmittingReview(true)
    setError(null)

    const url = reviewType === 'APPROVE' ? POLICY_APPROVE_URL : POLICY_REJECT_URL

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          change_id: reviewChangeId,
          reviewed_by_role: currentRole,
          reviewed_by_actor: currentActorId,
          review_reason: reviewReason.trim() || `Reviewed by ${currentRole}`,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || `Review action failed (HTTP ${res.status})`)
      }

      setActionSuccess(
        reviewType === 'APPROVE'
          ? `Change ${reviewChangeId} APPROVED! New active version ${data.version} created.`
          : `Change ${reviewChangeId} REJECTED.`
      )
      setReviewChangeId(null)
      setReviewReason('')
      fetchChanges()
    } catch (err: any) {
      setError(err.message || 'Review action failed')
    } finally {
      setSubmittingReview(false)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PENDING':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
      case 'APPROVED':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
      case 'REJECTED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40'
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Policy Change Review & Approval</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              Phase 6
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Controlled policy change workflow: Two-person rule, Security Admin approval gate, and strict no-self-approval enforcement.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setShowProposeModal(true)
              setError(null)
            }}
            className="flex items-center gap-2 px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-sm font-semibold transition shadow-md shadow-cyan-900/30"
          >
            <PlusCircle className="w-4 h-4" />
            Propose Change
          </button>
          <button
            onClick={fetchChanges}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm border border-slate-700 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Role Identity Bar */}
      <div className="flex items-center justify-between bg-slate-900/60 p-3.5 rounded-xl border border-slate-800 text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <Shield className="w-4 h-4 text-cyan-400" />
          <span>Acting Role: <strong className="text-white">{currentRole}</strong> ({currentActorId})</span>
        </div>
        <div className="text-slate-400">
          {isSecurityAdmin ? (
            <span className="text-emerald-400 font-semibold">Authorized to Approve / Reject changes</span>
          ) : (
            <span className="text-amber-400">Proposer mode: Approval restricted to SECURITY_ADMIN</span>
          )}
        </div>
      </div>

      {/* Success Alert */}
      {actionSuccess && (
        <div className="p-4 bg-emerald-950/40 border border-emerald-500/40 rounded-xl text-emerald-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-500/40 rounded-xl text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Change Requests Queue */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800">
            <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin text-cyan-400" />
            Loading policy change requests...
          </div>
        ) : changes.length === 0 ? (
          <div className="p-12 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800">
            <FileCheck2 className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            No policy change requests submitted yet. Click "Propose Change" to create one.
          </div>
        ) : (
          changes.map((chg) => {
            const isProposer = chg.requested_by_actor === currentActorId
            const isPending = chg.status === 'PENDING'

            return (
              <div
                key={chg.id}
                className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4 hover:border-slate-700 transition"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold text-white px-2.5 py-1 rounded bg-slate-800 border border-slate-700">
                      {chg.id}
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded text-xs font-bold border ${getStatusBadge(
                        chg.status
                      )}`}
                    >
                      {chg.status}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      {chg.current_version} → <strong className="text-cyan-400">{chg.proposed_version}</strong>
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(chg.requested_at).toLocaleString()}
                    </span>
                    <span className="flex items-center gap-1">
                      <User className="w-3.5 h-3.5 text-cyan-400" />
                      {chg.requested_by_role} ({chg.requested_by_actor})
                    </span>
                  </div>
                </div>

                {/* Proposed Transformation Card */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="md:col-span-2 space-y-2">
                    <div className="flex items-center gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <div className="font-mono font-bold text-white text-sm">
                        {chg.proposed_change.target}
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                          {chg.proposed_change.current_action}
                        </span>
                        <ArrowRight className="w-4 h-4 text-cyan-400" />
                        <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono font-bold border border-cyan-500/30">
                          {chg.proposed_change.proposed_action}
                        </span>
                      </div>
                    </div>

                    <div className="text-slate-300 text-xs">
                      <span className="text-slate-500 font-medium">Justification: </span>
                      {chg.reason}
                    </div>
                  </div>

                  {/* Review Actions or Review Info */}
                  <div className="flex flex-col justify-between items-start md:items-end gap-2 bg-slate-950/40 p-3 rounded-lg border border-slate-800/60">
                    {isPending ? (
                      <div className="w-full space-y-2">
                        {isSecurityAdmin ? (
                          isProposer ? (
                            <div className="text-amber-400 text-xs p-2 bg-amber-500/10 border border-amber-500/20 rounded">
                              ⚠️ <strong>SELF_APPROVAL_BLOCKED:</strong> You proposed this request. Independent review by another administrator is required.
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 justify-end w-full">
                              <button
                                onClick={() => {
                                  setReviewChangeId(chg.id)
                                  setReviewType('REJECT')
                                  setReviewReason('')
                                }}
                                className="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-semibold transition"
                              >
                                Reject
                              </button>
                              <button
                                onClick={() => {
                                  setReviewChangeId(chg.id)
                                  setReviewType('APPROVE')
                                  setReviewReason('')
                                }}
                                className="px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 rounded-lg text-xs font-bold transition shadow-md shadow-emerald-500/20"
                              >
                                Approve
                              </button>
                            </div>
                          )
                        ) : (
                          <div className="text-slate-500 text-xs italic text-right">
                            Approval restricted to SECURITY_ADMIN
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs space-y-1 text-right font-mono">
                        <div className="text-slate-400">
                          Reviewed by: <span className="text-white">{chg.reviewed_by_role}</span> ({chg.reviewed_by_actor})
                        </div>
                        {chg.reviewed_at && (
                          <div className="text-slate-500 text-[10px]">
                            {new Date(chg.reviewed_at).toLocaleString()}
                          </div>
                        )}
                        {chg.review_reason && (
                          <div className="text-slate-300 text-xs italic">
                            "{chg.review_reason}"
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Propose Change Modal */}
      {showProposeModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-bold text-white">Propose Policy Change</h3>
              </div>
              <button
                onClick={() => setShowProposeModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handlePropose} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Target Field or Category:</label>
                <input
                  type="text"
                  value={proposeTarget}
                  onChange={(e) => setProposeTarget(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-white focus:border-cyan-500 focus:outline-none"
                  placeholder="e.g. phone, gpa, DIRECT_IDENTIFIER"
                  required
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="isField"
                  checked={proposeIsField}
                  onChange={(e) => setProposeIsField(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0"
                />
                <label htmlFor="isField" className="text-slate-300">
                  Target is specific field name (uncheck if targeting a classification category)
                </label>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Proposed Protection Action:</label>
                <select
                  value={proposeAction}
                  onChange={(e) => setProposeAction(e.target.value as ProtectionAction)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-white focus:border-cyan-500 focus:outline-none"
                >
                  <option value="MASK">MASK (Partial redact e.g. ***-**-1234)</option>
                  <option value="GENERALIZE">GENERALIZE (Coarsen / Bucket)</option>
                  <option value="HASH">HASH (Cryptographic SHA-256)</option>
                  <option value="SUPPRESS">SUPPRESS (Full redaction)</option>
                  <option value="ENCRYPT">ENCRYPT (Ciphertext)</option>
                  <option value="NONE">NONE (Unrestricted)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Justification Reason (Audit Mandatory):</label>
                <textarea
                  value={proposeReason}
                  onChange={(e) => setProposeReason(e.target.value)}
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-white focus:border-cyan-500 focus:outline-none"
                  placeholder="Explain why this policy modification is requested and what analytical use case it supports..."
                  required
                />
              </div>

              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] text-slate-400">
                ℹ️ Proposing a change submits it in <strong className="text-amber-400">PENDING</strong> state. The active policy will <strong>NOT</strong> change until independently reviewed and approved by a Security Administrator.
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowProposeModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingPropose}
                  className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-bold transition shadow-md shadow-cyan-900/30"
                >
                  {submittingPropose ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      Submitting Proposal...
                    </>
                  ) : (
                    'Submit Proposal'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Review Modal (Approve or Reject) */}
      {reviewChangeId && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              {reviewType === 'APPROVE' ? (
                <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle className="w-6 h-6" />
                </div>
              ) : (
                <div className="p-2.5 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                  <XCircle className="w-6 h-6" />
                </div>
              )}
              <div>
                <h3 className="text-lg font-bold text-white">
                  {reviewType === 'APPROVE' ? 'Approve Policy Change' : 'Reject Policy Change'}
                </h3>
                <span className="text-xs text-slate-400 font-mono">{reviewChangeId}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Security Admin Review Rationale:
              </label>
              <textarea
                value={reviewReason}
                onChange={(e) => setReviewReason(e.target.value)}
                rows={2}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
                placeholder="Document approval rationale or rejection explanation..."
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setReviewChangeId(null)}
                disabled={submittingReview}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteReview}
                disabled={submittingReview}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition ${
                  reviewType === 'APPROVE'
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950'
                    : 'bg-rose-600 hover:bg-rose-500 text-white'
                }`}
              >
                {submittingReview ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Executing...
                  </>
                ) : reviewType === 'APPROVE' ? (
                  'Confirm Approval & Create Version'
                ) : (
                  'Confirm Rejection'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
export default ChangeReview
