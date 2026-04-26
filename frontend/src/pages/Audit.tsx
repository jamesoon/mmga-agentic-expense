import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface AuditEvent {
  id: number
  action: string
  actor: string
  oldValue: string | null
  newValue: string | null
  timestamp: string
}

interface AuditTimeline {
  claimId: string
  events: AuditEvent[]
}

const actorColor: Record<string, string> = {
  intake_agent: '#6366f1',
  abuse_guard: '#f59e0b',
  compliance_agent: '#34d399',
  fraud_agent: '#f87171',
  advisor_agent: '#60a5fa',
  system: '#9aa3b2',
}

export default function Audit() {
  const { claimId } = useParams<{ claimId: string }>()

  const { data, isLoading, error } = useQuery<AuditTimeline>({
    queryKey: ['audit', claimId],
    queryFn: () => apiFetch(`/api/audit/${claimId}/timeline`),
    enabled: !!claimId && claimId !== 'all',
  })

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
        Audit Timeline
        {claimId && claimId !== 'all' && (
          <span className="text-sm font-normal ml-2" style={{ color: 'var(--muted)' }}>
            Claim {claimId}
          </span>
        )}
      </h1>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading audit trail...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load audit trail.
        </div>
      )}

      {claimId === 'all' && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>
          Select a claim from the Manage page to view its audit trail.
        </div>
      )}

      {data?.events && (
        <div className="relative">
          {/* Vertical line */}
          <div
            className="absolute left-4 top-0 bottom-0 w-px"
            style={{ background: 'var(--border)' }}
          />

          <div className="space-y-6 pl-12">
            {data.events.map((event, idx) => {
              const dotColor = actorColor[event.actor] ?? '#9aa3b2'
              return (
                <div key={event.id ?? idx} className="relative">
                  {/* Dot */}
                  <div
                    className="absolute -left-10 top-1 w-3 h-3 rounded-full border-2"
                    style={{
                      background: dotColor,
                      borderColor: 'var(--bg)',
                      left: '-2.6rem',
                    }}
                  />

                  <div
                    className="rounded-xl border p-4"
                    style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>
                        {event.action}
                      </span>
                      <span className="text-xs" style={{ color: 'var(--muted)' }}>
                        {new Date(event.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="text-xs mb-2">
                      <span
                        className="px-1.5 py-0.5 rounded font-medium text-white"
                        style={{ background: dotColor }}
                      >
                        {event.actor}
                      </span>
                    </div>
                    {(event.oldValue || event.newValue) && (
                      <div className="grid grid-cols-2 gap-3 mt-2 text-xs" style={{ color: 'var(--muted)' }}>
                        {event.oldValue && (
                          <div>
                            <div className="font-medium mb-0.5">Before</div>
                            <div
                              className="rounded px-2 py-1 font-mono"
                              style={{ background: 'var(--bg)' }}
                            >
                              {event.oldValue}
                            </div>
                          </div>
                        )}
                        {event.newValue && (
                          <div>
                            <div className="font-medium mb-0.5">After</div>
                            <div
                              className="rounded px-2 py-1 font-mono"
                              style={{ background: 'var(--bg)' }}
                            >
                              {event.newValue}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {data?.events?.length === 0 && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>
          No audit events found for this claim.
        </div>
      )}
    </div>
  )
}
