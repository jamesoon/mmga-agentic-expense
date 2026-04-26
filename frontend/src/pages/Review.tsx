import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { BASE } from '../api/client'

interface ClaimDetail {
  id: number
  claimNumber: string
  employeeId: string
  status: string
  totalAmount: number
  currency: string
  createdAt: string
  receipts: ReceiptDetail[]
  complianceFindings: ComplianceFinding[] | null
  fraudFindings: FraudFinding[] | null
  advisorDecision: AdvisorDecision | null
}

interface ReceiptDetail {
  id: number
  merchant: string
  date: string
  totalAmount: number
  currency: string
  imagePath: string | null
}

interface ComplianceFinding {
  rule: string
  verdict: string
  detail: string
}

interface FraudFinding {
  signal: string
  severity: string
  detail: string
}

interface AdvisorDecision {
  decision: string
  reason: string
  reviewedBy: string | null
}

interface DecisionPayload {
  decision: 'approved' | 'rejected' | 'escalated'
  reason: string
}

const statusColor: Record<string, string> = {
  approved: '#34d399',
  rejected: '#f87171',
  submitted: '#facc15',
  draft: '#60a5fa',
  escalated: '#fb923c',
}

const reviewerRoles = ['reviewer', 'manager', 'director', 'admin']

export default function Review() {
  const { claimId } = useParams<{ claimId: string }>()
  const user = useAuthStore((s) => s.user)
  const qc = useQueryClient()
  const [decision, setDecision] = useState<'approved' | 'rejected' | 'escalated'>('approved')
  const [reason, setReason] = useState('')

  const { data: claim, isLoading, error } = useQuery<ClaimDetail>({
    queryKey: ['review', claimId],
    queryFn: () => apiFetch(`/api/review/${claimId}`),
    enabled: !!claimId,
  })

  const mutation = useMutation({
    mutationFn: (payload: DecisionPayload) =>
      apiFetch(`/api/review/${claimId}/decision`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review', claimId] })
      setReason('')
    },
  })

  const canReview = user && reviewerRoles.includes(user.role)
  const receiptImageUrl = (imagePath: string | null) =>
    imagePath ? `${BASE}/api/review/${claimId}/receipt-image` : null

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-sm" style={{ color: 'var(--muted)' }}>
        Loading claim...
      </div>
    )
  }

  if (error || !claim) {
    return (
      <div className="text-sm" style={{ color: 'var(--danger)' }}>
        Failed to load claim.
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
          Claim {claim.claimNumber}
        </h1>
        <span
          className="px-2 py-0.5 rounded text-xs font-semibold capitalize"
          style={{
            background: (statusColor[claim.status] ?? '#9aa3b2') + '22',
            color: statusColor[claim.status] ?? 'var(--muted)',
          }}
        >
          {claim.status}
        </span>
      </div>

      {/* Claim details */}
      <div
        className="rounded-xl border p-5 grid grid-cols-2 gap-4 text-sm"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        {[
          ['Employee ID', claim.employeeId],
          ['Total Amount', `${claim.currency} ${claim.totalAmount?.toFixed(2)}`],
          ['Status', claim.status],
          ['Submitted', new Date(claim.createdAt).toLocaleString()],
        ].map(([label, value]) => (
          <div key={label}>
            <div className="text-xs font-medium mb-1" style={{ color: 'var(--muted)' }}>{label}</div>
            <div style={{ color: 'var(--fg)' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Receipts */}
      {claim.receipts?.length > 0 && (
        <div className="rounded-xl border" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          <div className="px-5 py-3 border-b text-sm font-semibold" style={{ borderColor: 'var(--border)', color: 'var(--fg)' }}>
            Receipts
          </div>
          {claim.receipts.map((receipt) => {
            const imgUrl = receiptImageUrl(receipt.imagePath)
            return (
              <div key={receipt.id} className="p-5 border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                <div className="flex gap-6">
                  {imgUrl && (
                    <img
                      src={imgUrl}
                      alt="Receipt"
                      className="w-32 h-32 object-cover rounded-lg border"
                      style={{ borderColor: 'var(--border)' }}
                    />
                  )}
                  <div className="flex-1 grid grid-cols-2 gap-3 text-sm">
                    {[
                      ['Merchant', receipt.merchant],
                      ['Date', receipt.date],
                      ['Amount', `${receipt.currency} ${receipt.totalAmount?.toFixed(2)}`],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <div className="text-xs font-medium mb-1" style={{ color: 'var(--muted)' }}>{label}</div>
                        <div style={{ color: 'var(--fg)' }}>{value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Compliance findings */}
      {claim.complianceFindings && claim.complianceFindings.length > 0 && (
        <div className="rounded-xl border" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          <div className="px-5 py-3 border-b text-sm font-semibold" style={{ borderColor: 'var(--border)', color: 'var(--fg)' }}>
            Compliance Findings
          </div>
          <div className="p-5 space-y-3">
            {claim.complianceFindings.map((f, i) => (
              <div
                key={i}
                className="rounded-lg border p-3 text-sm"
                style={{ borderColor: 'var(--border)', background: '#1a1f35' }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium" style={{ color: 'var(--fg)' }}>{f.rule}</span>
                  <span
                    className="px-1.5 py-0.5 rounded text-xs font-medium"
                    style={{
                      background: f.verdict === 'pass' ? '#0d1f15' : '#1f1215',
                      color: f.verdict === 'pass' ? 'var(--success)' : 'var(--danger)',
                    }}
                  >
                    {f.verdict}
                  </span>
                </div>
                <p style={{ color: 'var(--muted)' }}>{f.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fraud findings */}
      {claim.fraudFindings && claim.fraudFindings.length > 0 && (
        <div className="rounded-xl border" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          <div className="px-5 py-3 border-b text-sm font-semibold" style={{ borderColor: 'var(--border)', color: 'var(--fg)' }}>
            Fraud Signals
          </div>
          <div className="p-5 space-y-3">
            {claim.fraudFindings.map((f, i) => (
              <div
                key={i}
                className="rounded-lg border p-3 text-sm"
                style={{ borderColor: 'var(--border)', background: '#1a1f35' }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium" style={{ color: 'var(--fg)' }}>{f.signal}</span>
                  <span
                    className="px-1.5 py-0.5 rounded text-xs font-medium"
                    style={{
                      background: f.severity === 'high' ? '#1f1215' : '#1f1a0d',
                      color: f.severity === 'high' ? 'var(--danger)' : 'var(--warning)',
                    }}
                  >
                    {f.severity}
                  </span>
                </div>
                <p style={{ color: 'var(--muted)' }}>{f.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Advisor decision */}
      {claim.advisorDecision && (
        <div className="rounded-xl border p-5 text-sm" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          <div className="text-sm font-semibold mb-3" style={{ color: 'var(--fg)' }}>Advisor Decision</div>
          <div className="space-y-2">
            <div>
              <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Decision: </span>
              <span className="font-semibold capitalize" style={{ color: 'var(--fg)' }}>
                {claim.advisorDecision.decision}
              </span>
            </div>
            <div>
              <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Reason: </span>
              <span style={{ color: 'var(--fg)' }}>{claim.advisorDecision.reason}</span>
            </div>
          </div>
        </div>
      )}

      {/* Reviewer action */}
      {canReview && (
        <div className="rounded-xl border p-5" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--fg)' }}>
            Record Decision
          </h2>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
                Decision
              </label>
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value as typeof decision)}
                className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
                style={{
                  background: 'var(--bg)',
                  borderColor: 'var(--border)',
                  color: 'var(--fg)',
                }}
              >
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="escalated">Escalated</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
                Reason
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none resize-none"
                style={{
                  background: 'var(--bg)',
                  borderColor: 'var(--border)',
                  color: 'var(--fg)',
                }}
                placeholder="Add a reason for this decision..."
              />
            </div>
            <button
              onClick={() => mutation.mutate({ decision, reason })}
              disabled={mutation.isPending}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-60"
              style={{ background: 'var(--accent)' }}
            >
              {mutation.isPending ? 'Submitting...' : 'Submit decision'}
            </button>
            {mutation.isError && (
              <div className="text-xs" style={{ color: 'var(--danger)' }}>
                {(mutation.error as Error).message}
              </div>
            )}
            {mutation.isSuccess && (
              <div className="text-xs" style={{ color: 'var(--success)' }}>
                Decision recorded.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
