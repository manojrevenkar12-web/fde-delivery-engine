export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`

const REASON: Record<string, string> = {
  unblock: 'Unblock',
  change_request: 'Change request',
  capacity: 'Capacity',
  relationship: 'Relationship',
  none: 'Watch',
}
export const kind = (k: string) => REASON[k] ?? k

export function signalTags(s: { blocker: boolean; data_access: boolean; scope_change: boolean; sentiment: number }): string[] {
  const tags: string[] = []
  if (s.blocker) tags.push(s.data_access ? 'Blocked on access' : 'Blocked')
  if (s.scope_change) tags.push('New scope')
  if (s.sentiment < 0) tags.push('Customer unhappy')
  if (s.sentiment > 0) tags.push('Customer happy')
  return tags
}
