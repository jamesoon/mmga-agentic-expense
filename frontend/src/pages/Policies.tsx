import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { RefreshCw } from 'lucide-react'

interface PolicySection {
  id: string
  category: string
  section: string
  text: string
  file: string
}

interface PoliciesResponse {
  sections: PolicySection[]
  lastIngested: string | null
}

interface ReingestResponse {
  message: string
  count: number
}

export default function Policies() {
  const qc = useQueryClient()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery<PoliciesResponse>({
    queryKey: ['policies'],
    queryFn: () => apiFetch('/policies/sections'),
  })

  const reingestMutation = useMutation<ReingestResponse>({
    mutationFn: () =>
      apiFetch('/reingest', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['policies'] })
    },
  })

  const categoryColors: Record<string, string> = {
    meals: '#6366f1',
    transport: '#34d399',
    accommodation: '#f59e0b',
    office_supplies: '#60a5fa',
    general: '#9aa3b2',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
            Policies
          </h1>
          {data?.lastIngested && (
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
              Last ingested: {new Date(data.lastIngested).toLocaleString()}
            </p>
          )}
        </div>

        <button
          onClick={() => reingestMutation.mutate()}
          disabled={reingestMutation.isPending}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-opacity hover:opacity-80 disabled:opacity-60"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        >
          <RefreshCw size={14} className={reingestMutation.isPending ? 'animate-spin' : ''} />
          {reingestMutation.isPending ? 'Re-ingesting...' : 'Re-ingest'}
        </button>
      </div>

      {reingestMutation.isSuccess && (
        <div
          className="rounded-lg px-3 py-2 text-sm border"
          style={{ background: '#0d1f15', borderColor: '#1a5c35', color: 'var(--success)' }}
        >
          Re-ingested {reingestMutation.data?.count ?? 0} policy sections successfully.
        </div>
      )}

      {reingestMutation.isError && (
        <div
          className="rounded-lg px-3 py-2 text-sm border"
          style={{ background: '#1f1215', borderColor: '#5c2025', color: 'var(--danger)' }}
        >
          {(reingestMutation.error as Error).message}
        </div>
      )}

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading policies...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load policies.
        </div>
      )}

      {data?.sections && (
        <div className="space-y-2">
          {data.sections.map((section) => (
            <div
              key={section.id}
              className="rounded-xl border overflow-hidden"
              style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
            >
              <button
                className="w-full flex items-center justify-between px-5 py-3 text-left hover:opacity-80 transition-opacity"
                onClick={() => setExpandedId(expandedId === section.id ? null : section.id)}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="px-2 py-0.5 rounded text-xs font-semibold text-white"
                    style={{ background: categoryColors[section.category] ?? '#9aa3b2' }}
                  >
                    {section.category}
                  </span>
                  <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                    {section.section}
                  </span>
                </div>
                <span className="text-xs" style={{ color: 'var(--muted)' }}>
                  {section.file}
                </span>
              </button>

              {expandedId === section.id && (
                <div
                  className="px-5 pb-4 text-sm border-t"
                  style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
                >
                  <pre className="whitespace-pre-wrap font-sans mt-3 leading-relaxed">
                    {section.text}
                  </pre>
                </div>
              )}
            </div>
          ))}

          {data.sections.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--muted)' }}>
              No policy sections loaded. Click Re-ingest to load them.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
