import { config } from './tokens.ts'
import type { EngagementDetail, EngagementSummary, GateResult, Note, Report, Review, Team } from './types.ts'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'X-Api-Key': config.apiKey, 'content-type': 'application/json', ...(init?.headers ?? {}) },
  })
  const text = await res.text()
  const body = text ? JSON.parse(text) : {}
  if (!res.ok) throw new Error(body.error ?? `The server answered ${res.status}.`)
  return body as T
}

export const api = {
  engagements: () => call<{ week: number; engagements: EngagementSummary[] }>('/api/engagements'),
  engagement: (id: string) => call<EngagementDetail>(`/api/engagements/${encodeURIComponent(id)}`),
  addNote: (id: string, text: string) =>
    call<Pick<Note, 'signals'> & { decision: NonNullable<Note['decision']> }>(
      `/api/engagements/${encodeURIComponent(id)}/notes`,
      { method: 'POST', body: JSON.stringify({ text }) },
    ),
  team: () => call<Team>('/api/team'),
  replan: () => call<Team>('/api/plan', { method: 'POST' }),
  reviews: () => call<{ reviews: Review[] }>('/api/reviews'),
  runReview: (id: string) => call<GateResult>(`/api/reviews/${encodeURIComponent(id)}/run`, { method: 'POST', body: '{}' }),
  results: () => call<{ dev: Report | null; heldout: Report | null }>('/api/results'),
}
