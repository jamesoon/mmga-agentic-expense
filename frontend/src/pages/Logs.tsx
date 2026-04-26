import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { RefreshCw } from 'lucide-react'

interface LogEntry {
  timestamp: string
  level: 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG'
  service: string
  message: string
  detail?: string
}

interface LogsResponse {
  logs: LogEntry[]
  services: string[]
}

const levelBadge: Record<string, { bg: string; text: string }> = {
  ERROR: { bg: '#5c2025', text: '#f87171' },
  WARNING: { bg: '#5c4a10', text: '#facc15' },
  INFO: { bg: '#102040', text: '#60a5fa' },
  DEBUG: { bg: '#1a1f35', text: '#9aa3b2' },
}

export default function Logs() {
  const [levelFilter, setLevelFilter] = useState<string>('ALL')
  const [serviceFilter, setServiceFilter] = useState<string>('ALL')

  const { data, isLoading, error, refetch, isFetching } = useQuery<LogsResponse>({
    queryKey: ['logs'],
    queryFn: () => apiFetch('/logs/json'),
    refetchInterval: 60_000,
  })

  const levels = ['ALL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
  const services = data?.services ? ['ALL', ...data.services] : ['ALL']

  const filteredLogs = data?.logs?.filter((log) => {
    const levelMatch = levelFilter === 'ALL' || log.level === levelFilter
    const serviceMatch = serviceFilter === 'ALL' || log.service === serviceFilter
    return levelMatch && serviceMatch
  }) ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
          Logs
        </h1>
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

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: 'var(--muted)' }}>
            Level
          </label>
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            className="rounded-lg px-3 py-1.5 text-sm border outline-none"
            style={{ background: 'var(--bg)', borderColor: 'var(--border)', color: 'var(--fg)' }}
          >
            {levels.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: 'var(--muted)' }}>
            Service
          </label>
          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="rounded-lg px-3 py-1.5 text-sm border outline-none"
            style={{ background: 'var(--bg)', borderColor: 'var(--border)', color: 'var(--fg)' }}
          >
            {services.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading logs...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load logs.
        </div>
      )}

      {data && (
        <div
          className="rounded-xl border overflow-hidden"
          style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: `1px solid var(--border)` }}>
                  {['Time', 'Level', 'Service', 'Message'].map((h) => (
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
                {filteredLogs.map((log, idx) => {
                  const badge = levelBadge[log.level] ?? levelBadge['DEBUG']
                  return (
                    <tr
                      key={idx}
                      className="border-b last:border-0"
                      style={{ borderColor: 'var(--border)' }}
                    >
                      <td className="px-4 py-2.5 whitespace-nowrap font-mono text-xs" style={{ color: 'var(--muted)' }}>
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className="px-1.5 py-0.5 rounded text-xs font-semibold"
                          style={{ background: badge.bg, color: badge.text }}
                        >
                          {log.level}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--muted)' }}>
                        {log.service}
                      </td>
                      <td className="px-4 py-2.5" style={{ color: 'var(--fg)' }}>
                        <div>{log.message}</div>
                        {log.detail && (
                          <div className="text-xs mt-0.5 font-mono" style={{ color: 'var(--muted)' }}>
                            {log.detail}
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {filteredLogs.length === 0 && (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
                No log entries match the current filters.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
