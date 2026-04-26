import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface EvalRun {
  id: string
  runAt: string
  model: string
  totalClaims: number
  avgScore: number
  passRate: number
  status: 'complete' | 'running' | 'failed'
}

interface EvalResult {
  claimId: string
  claimNumber: string
  score: number
  verdict: string
  justification: string
  selfConsistency: number | null
  crossModalMatch: boolean | null
  verifierDisagreement: boolean | null
}

interface RunDetail {
  run: EvalRun
  results: EvalResult[]
}

interface RunsResponse {
  runs: EvalRun[]
}

const verdictColor: Record<string, string> = {
  pass: '#34d399',
  fail: '#f87171',
  review: '#facc15',
}

const statusBadge: Record<string, { bg: string; text: string }> = {
  complete: { bg: '#0d1f15', text: '#34d399' },
  running: { bg: '#102040', text: '#60a5fa' },
  failed: { bg: '#1f1215', text: '#f87171' },
}

export default function LlmAsJudge() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const { data: runsData, isLoading, error } = useQuery<RunsResponse>({
    queryKey: ['llmasjudge-runs'],
    queryFn: () => apiFetch('/llmasjudge/runs'),
  })

  const { data: runDetail, isLoading: detailLoading } = useQuery<RunDetail>({
    queryKey: ['llmasjudge-run', selectedRunId],
    queryFn: () => apiFetch(`/llmasjudge/runs/${selectedRunId}`),
    enabled: !!selectedRunId,
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>
        LLM as Judge
      </h1>
      <p className="text-sm" style={{ color: 'var(--muted)' }}>
        Evaluation harness results — LLM-based scoring across self-consistency, cross-modal grounding, and verifier-disagreement signals.
      </p>

      {isLoading && (
        <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading eval runs...</div>
      )}

      {error && (
        <div className="text-sm" style={{ color: 'var(--danger)' }}>
          Failed to load eval runs.
        </div>
      )}

      {runsData && (
        <div
          className="rounded-xl border"
          style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
        >
          <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <h2 className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>
              Eval Run History
            </h2>
          </div>
          {!runsData.runs?.length ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
              No eval runs found.
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {runsData.runs.map((run) => {
                const isSelected = selectedRunId === run.id
                const badge = statusBadge[run.status] ?? statusBadge.failed
                return (
                  <div key={run.id}>
                    <button
                      className="w-full flex items-center gap-3 px-5 py-4 text-left hover:opacity-80 transition-opacity"
                      onClick={() => setSelectedRunId(isSelected ? null : run.id)}
                    >
                      <span style={{ color: 'var(--muted)' }}>
                        {isSelected ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                            {new Date(run.runAt).toLocaleString()}
                          </span>
                          <span
                            className="px-1.5 py-0.5 rounded text-xs font-semibold"
                            style={{ background: badge.bg, color: badge.text }}
                          >
                            {run.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                          <span>Model: {run.model}</span>
                          <span>Claims: {run.totalClaims}</span>
                          <span>Avg score: {run.avgScore?.toFixed(2)}</span>
                          <span>Pass rate: {((run.passRate ?? 0) * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    </button>

                    {isSelected && (
                      <div
                        className="px-5 pb-4 border-t"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        {detailLoading ? (
                          <div className="py-4 text-sm" style={{ color: 'var(--muted)' }}>
                            Loading results...
                          </div>
                        ) : runDetail?.results?.length ? (
                          <div className="mt-4 overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr style={{ borderBottom: `1px solid var(--border)` }}>
                                  {['Claim', 'Score', 'Verdict', 'Self-Consistency', 'Cross-Modal', 'Verifier Disagree', 'Justification'].map((h) => (
                                    <th
                                      key={h}
                                      className="px-3 py-2 text-left text-xs font-medium whitespace-nowrap"
                                      style={{ color: 'var(--muted)' }}
                                    >
                                      {h}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {runDetail.results.map((result) => (
                                  <tr
                                    key={result.claimId}
                                    className="border-b last:border-0"
                                    style={{ borderColor: 'var(--border)' }}
                                  >
                                    <td className="px-3 py-2.5 font-medium" style={{ color: 'var(--accent)' }}>
                                      {result.claimNumber}
                                    </td>
                                    <td className="px-3 py-2.5" style={{ color: 'var(--fg)' }}>
                                      {result.score?.toFixed(2)}
                                    </td>
                                    <td className="px-3 py-2.5">
                                      <span
                                        className="font-semibold capitalize"
                                        style={{ color: verdictColor[result.verdict] ?? 'var(--muted)' }}
                                      >
                                        {result.verdict}
                                      </span>
                                    </td>
                                    <td className="px-3 py-2.5" style={{ color: 'var(--muted)' }}>
                                      {result.selfConsistency !== null ? result.selfConsistency?.toFixed(2) : '—'}
                                    </td>
                                    <td className="px-3 py-2.5" style={{ color: 'var(--muted)' }}>
                                      {result.crossModalMatch === null ? '—' : result.crossModalMatch ? 'Yes' : 'No'}
                                    </td>
                                    <td className="px-3 py-2.5" style={{ color: 'var(--muted)' }}>
                                      {result.verifierDisagreement === null ? '—' : result.verifierDisagreement ? 'Yes' : 'No'}
                                    </td>
                                    <td
                                      className="px-3 py-2.5 max-w-xs text-xs"
                                      style={{ color: 'var(--muted)' }}
                                    >
                                      <span className="line-clamp-2" title={result.justification}>
                                        {result.justification}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="py-4 text-sm" style={{ color: 'var(--muted)' }}>
                            No results for this run.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
