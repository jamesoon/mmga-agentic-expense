import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { Link } from 'react-router-dom'

interface ClaimSummary {
  id: number
  claimNumber: string
  employeeId: string
  status: string
  totalAmount: number
  currency: string
  createdAt: string
}

interface ClaimsListResponse {
  claims: ClaimSummary[]
}

interface BulkActionPayload {
  ids: number[]
  action: 'approve' | 'reject' | 'flag'
}

const statusColor: Record<string, string> = {
  approved: '#34d399',
  rejected: '#f87171',
  submitted: '#facc15',
  draft: '#60a5fa',
  escalated: '#fb923c',
}

export default function Manage() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkAction, setBulkAction] = useState<'approve' | 'reject' | 'flag'>('approve')

  const { data, isLoading, error } = useQuery<ClaimsListResponse>({
    queryKey: ['manage-claims'],
    queryFn: () => apiFetch('/api/audit/claims'),
  })

  const bulkMutation = useMutation({
    mutationFn: (payload: BulkActionPayload) =>
      apiFetch('/api/manage/bulk-action', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['manage-claims'] })
      setSelected(new Set())
    },
  })

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (!data?.claims) return
    if (selected.size === data.claims.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(data.claims.map((c) => c.id)))
    }
  }

  const handleBulk = () => {
    if (selected.size === 0) return
    bulkMutation.mutate({ ids: Array.from(selected), action: bulkAction })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
        Manage Claims
      </h1>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load claims.
        </div>
      )}

      {data && (
        <>
          {/* Bulk actions */}
          {selected.size > 0 && (
            <div
              className="flex items-center gap-3 p-3 rounded-xl border"
              style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
            >
              <span className="text-sm" style={{ color: 'var(--muted)' }}>
                {selected.size} selected
              </span>
              <select
                value={bulkAction}
                onChange={(e) => setBulkAction(e.target.value as typeof bulkAction)}
                className="rounded-lg px-2 py-1.5 text-sm border outline-none"
                style={{
                  background: 'var(--bg)',
                  borderColor: 'var(--border)',
                  color: 'var(--fg)',
                }}
              >
                <option value="approve">Approve</option>
                <option value="reject">Reject</option>
                <option value="flag">Flag</option>
              </select>
              <button
                onClick={handleBulk}
                disabled={bulkMutation.isPending}
                className="px-3 py-1.5 rounded-lg text-sm font-semibold text-white disabled:opacity-60"
                style={{ background: 'var(--accent)' }}
              >
                {bulkMutation.isPending ? 'Processing...' : 'Apply'}
              </button>
              <button
                onClick={() => setSelected(new Set())}
                className="text-sm hover:underline"
                style={{ color: 'var(--muted)' }}
              >
                Clear
              </button>
            </div>
          )}

          {bulkMutation.isError && (
            <div className="text-sm" style={{ color: 'var(--danger)' }}>
              {(bulkMutation.error as Error).message}
            </div>
          )}

          {/* Table */}
          <div
            className="rounded-xl border"
            style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: `1px solid var(--border)` }}>
                    <th className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={!!data.claims?.length && selected.size === data.claims.length}
                        onChange={toggleAll}
                        className="accent-indigo-500"
                      />
                    </th>
                    {['Claim #', 'Employee', 'Status', 'Amount', 'Date', 'Actions'].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left text-xs font-medium"
                        style={{ color: 'var(--muted)' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.claims?.map((claim) => (
                    <tr
                      key={claim.id}
                      className="border-b last:border-0 hover:opacity-80 transition-opacity"
                      style={{ borderColor: 'var(--border)' }}
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(claim.id)}
                          onChange={() => toggleSelect(claim.id)}
                          className="accent-indigo-500"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/review/${claim.id}`}
                          className="hover:underline font-medium"
                          style={{ color: 'var(--accent)' }}
                        >
                          {claim.claimNumber}
                        </Link>
                      </td>
                      <td className="px-4 py-3" style={{ color: 'var(--fg)' }}>
                        {claim.employeeId}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="font-medium capitalize"
                          style={{ color: statusColor[claim.status] ?? 'var(--muted)' }}
                        >
                          {claim.status}
                        </span>
                      </td>
                      <td className="px-4 py-3" style={{ color: 'var(--fg)' }}>
                        {claim.currency} {claim.totalAmount?.toFixed(2)}
                      </td>
                      <td className="px-4 py-3" style={{ color: 'var(--muted)' }}>
                        {new Date(claim.createdAt).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/review/${claim.id}`}
                            className="text-xs hover:underline"
                            style={{ color: 'var(--accent)' }}
                          >
                            Review
                          </Link>
                          <Link
                            to={`/audit/${claim.id}`}
                            className="text-xs hover:underline"
                            style={{ color: 'var(--muted)' }}
                          >
                            Audit
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {!data.claims?.length && (
                <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
                  No claims found.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
