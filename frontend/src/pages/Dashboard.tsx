import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { Link } from 'react-router-dom'

interface KpiData {
  totalClaims: number
  pending: number
  approved: number
  rejected: number
}

interface ClaimRow {
  id: number
  claimNumber: string
  employeeId: string
  status: string
  totalAmount: number
  currency: string
  createdAt: string
}

interface ClaimsResponse {
  claims: ClaimRow[]
}

const statusColor: Record<string, string> = {
  approved: 'text-green-400',
  rejected: 'text-red-400',
  submitted: 'text-yellow-400',
  draft: 'text-blue-400',
  escalated: 'text-orange-400',
}

export default function Dashboard() {
  const { data: kpis, isLoading: kpisLoading } = useQuery<KpiData>({
    queryKey: ['dashboard-kpis'],
    queryFn: () => apiFetch('/api/dashboard/kpis'),
  })

  const { data: claimsData, isLoading: claimsLoading } = useQuery<ClaimsResponse>({
    queryKey: ['dashboard-claims'],
    queryFn: () => apiFetch('/api/dashboard/claims'),
  })

  const kpiCards = [
    { label: 'Total Claims', value: kpis?.totalClaims ?? 0, color: 'text-indigo-400' },
    { label: 'Pending', value: kpis?.pending ?? 0, color: 'text-yellow-400' },
    { label: 'Approved', value: kpis?.approved ?? 0, color: 'text-green-400' },
    { label: 'Rejected', value: kpis?.rejected ?? 0, color: 'text-red-400' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
        Dashboard
      </h1>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpiCards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border p-5"
            style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
          >
            <div className="text-xs font-medium mb-2" style={{ color: 'var(--muted)' }}>
              {card.label}
            </div>
            {kpisLoading ? (
              <div className="h-8 w-16 rounded animate-pulse" style={{ background: 'var(--border)' }} />
            ) : (
              <div className={`text-3xl font-bold ${card.color}`}>{card.value}</div>
            )}
          </div>
        ))}
      </div>

      {/* Claims table */}
      <div
        className="rounded-xl border"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>
            Recent Claims
          </h2>
        </div>

        {claimsLoading ? (
          <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
            Loading claims...
          </div>
        ) : !claimsData?.claims?.length ? (
          <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
            No claims yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: `1px solid var(--border)` }}>
                  {['Claim #', 'Employee', 'Status', 'Amount', 'Date'].map((h) => (
                    <th
                      key={h}
                      className="px-5 py-3 text-left text-xs font-medium"
                      style={{ color: 'var(--muted)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {claimsData.claims.map((claim) => (
                  <tr
                    key={claim.id}
                    className="border-b last:border-0 hover:opacity-80 transition-opacity"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    <td className="px-5 py-3">
                      <Link
                        to={`/review/${claim.id}`}
                        className="hover:underline font-medium"
                        style={{ color: 'var(--accent)' }}
                      >
                        {claim.claimNumber}
                      </Link>
                    </td>
                    <td className="px-5 py-3" style={{ color: 'var(--fg)' }}>
                      {claim.employeeId}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`font-medium capitalize ${statusColor[claim.status] ?? 'text-gray-400'}`}>
                        {claim.status}
                      </span>
                    </td>
                    <td className="px-5 py-3" style={{ color: 'var(--fg)' }}>
                      {claim.currency} {claim.totalAmount?.toFixed(2)}
                    </td>
                    <td className="px-5 py-3" style={{ color: 'var(--muted)' }}>
                      {new Date(claim.createdAt).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
