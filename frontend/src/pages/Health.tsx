import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react'

type ServiceStatus = 'healthy' | 'unhealthy' | 'degraded' | 'unknown'

interface ServiceCheck {
  name: string
  status: ServiceStatus
  latencyMs?: number
  detail?: string
}

interface HealthData {
  overall: ServiceStatus
  checks: ServiceCheck[]
  timestamp: string
}

const statusIcon: Record<ServiceStatus, React.ReactNode> = {
  healthy: <CheckCircle size={16} className="text-green-400" />,
  unhealthy: <XCircle size={16} className="text-red-400" />,
  degraded: <AlertCircle size={16} className="text-yellow-400" />,
  unknown: <AlertCircle size={16} className="text-gray-400" />,
}

const statusBg: Record<ServiceStatus, string> = {
  healthy: '#0d1f15',
  unhealthy: '#1f1215',
  degraded: '#1f1a0d',
  unknown: '#1a1a1a',
}

const statusBorder: Record<ServiceStatus, string> = {
  healthy: '#1a5c35',
  unhealthy: '#5c2025',
  degraded: '#5c4a10',
  unknown: '#333',
}

export default function Health() {
  const { data, isLoading, error, refetch, isFetching } = useQuery<HealthData>({
    queryKey: ['health'],
    queryFn: () => apiFetch('/health/json'),
    refetchInterval: 30_000,
  })

  const overallColor: Record<ServiceStatus, string> = {
    healthy: 'text-green-400',
    unhealthy: 'text-red-400',
    degraded: 'text-yellow-400',
    unknown: 'text-gray-400',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
            System Health
          </h1>
          {data?.timestamp && (
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
              Last checked: {new Date(data.timestamp).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-opacity hover:opacity-80 disabled:opacity-60"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Checking services...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load health data.
        </div>
      )}

      {data && (
        <>
          {/* Overall status */}
          <div
            className="rounded-xl border p-5 flex items-center gap-3"
            style={{
              background: statusBg[data.overall] ?? 'var(--card)',
              borderColor: statusBorder[data.overall] ?? 'var(--border)',
            }}
          >
            {statusIcon[data.overall]}
            <div>
              <div className={`text-sm font-semibold capitalize ${overallColor[data.overall]}`}>
                System {data.overall}
              </div>
              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                {data.checks?.length ?? 0} services checked
              </div>
            </div>
          </div>

          {/* Service cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.checks?.map((check) => (
              <div
                key={check.name}
                className="rounded-xl border p-4"
                style={{
                  background: statusBg[check.status] ?? 'var(--card)',
                  borderColor: statusBorder[check.status] ?? 'var(--border)',
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>
                    {check.name}
                  </span>
                  {statusIcon[check.status]}
                </div>
                <div
                  className="text-xs capitalize font-medium"
                  style={{
                    color:
                      check.status === 'healthy'
                        ? 'var(--success)'
                        : check.status === 'unhealthy'
                        ? 'var(--danger)'
                        : 'var(--warning)',
                  }}
                >
                  {check.status}
                </div>
                {check.latencyMs !== undefined && (
                  <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                    {check.latencyMs}ms
                  </div>
                )}
                {check.detail && (
                  <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                    {check.detail}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
