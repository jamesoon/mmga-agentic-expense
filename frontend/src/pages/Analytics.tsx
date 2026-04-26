import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface EfficiencyData {
  avgProcessingMinutes: number
  claimsProcessedToday: number
  approvalRate: number
  automationRate: number
  byCategory: CategoryStat[]
}

interface CategoryStat {
  category: string
  count: number
  avgAmount: number
  approvalRate: number
}

export default function Analytics() {
  const { data, isLoading, error } = useQuery<EfficiencyData>({
    queryKey: ['analytics-efficiency'],
    queryFn: () => apiFetch('/api/dashboard/efficiency'),
  })

  const statCards = data
    ? [
        { label: 'Avg Processing Time', value: `${data.avgProcessingMinutes?.toFixed(1)} min` },
        { label: 'Claims Today', value: String(data.claimsProcessedToday ?? 0) },
        { label: 'Approval Rate', value: `${((data.approvalRate ?? 0) * 100).toFixed(1)}%` },
        { label: 'Automation Rate', value: `${((data.automationRate ?? 0) * 100).toFixed(1)}%` },
      ]
    : []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
        Analytics
      </h1>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load analytics data.
        </div>
      )}

      {data && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map((card) => (
              <div
                key={card.label}
                className="rounded-xl border p-5"
                style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
              >
                <div className="text-xs font-medium mb-2" style={{ color: 'var(--muted)' }}>
                  {card.label}
                </div>
                <div className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                  {card.value}
                </div>
              </div>
            ))}
          </div>

          {/* Category breakdown */}
          {data.byCategory?.length > 0 && (
            <div
              className="rounded-xl border"
              style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
            >
              <div
                className="px-5 py-4 border-b text-sm font-semibold"
                style={{ borderColor: 'var(--border)', color: 'var(--fg)' }}
              >
                Breakdown by Category
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: `1px solid var(--border)` }}>
                      {['Category', 'Claims', 'Avg Amount (SGD)', 'Approval Rate'].map((h) => (
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
                    {data.byCategory.map((row) => (
                      <tr
                        key={row.category}
                        className="border-b last:border-0"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <td className="px-5 py-3 capitalize font-medium" style={{ color: 'var(--fg)' }}>
                          {row.category}
                        </td>
                        <td className="px-5 py-3" style={{ color: 'var(--fg)' }}>
                          {row.count}
                        </td>
                        <td className="px-5 py-3" style={{ color: 'var(--fg)' }}>
                          {row.avgAmount?.toFixed(2)}
                        </td>
                        <td className="px-5 py-3" style={{ color: 'var(--fg)' }}>
                          {((row.approvalRate ?? 0) * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
