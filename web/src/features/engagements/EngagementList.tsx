import { PHASE_LABEL } from '../../shared/tokens.ts'
import type { EngagementSummary } from '../../shared/types.ts'
import { EmptyState, ErrorState, Skeleton } from '../../shared/ui/States.tsx'
import styles from './Engagements.module.css'

interface Props {
  rows: EngagementSummary[] | undefined
  loading: boolean
  error: string | undefined
  onRetry: () => void
  selected: string | undefined
  onSelect: (id: string) => void
}

/** Live engagements, riskiest first; finished ones stay below for reference. */
export function EngagementList({ rows, loading, error, onRetry, selected, onSelect }: Props) {
  if (loading && !rows) return <Skeleton label="Loading engagements" />
  if (error) return <ErrorState what="The engagements" message={error} onRetry={onRetry} />
  if (!rows || rows.length === 0)
    return <EmptyState title="No engagements yet." hint="Accepted opportunities appear here once discovery starts." />
  return (
    <ol className={styles.list} aria-label="Engagements">
      {rows.map((r) => {
        const late = !r.done && r.weeksLeft < 0
        return (
          <li key={r.id}>
            <button
              type="button"
              className={styles.row}
              aria-current={r.id === selected ? 'true' : undefined}
              onClick={() => onSelect(r.id)}
            >
              <span className={styles.customer}>{r.customer}</span>
              <span className={r.escalatedWeek !== null && !r.done ? styles.flagged : styles.quiet}>
                {r.done ? 'Done' : r.escalatedWeek !== null ? 'Escalated' : late ? 'Late' : PHASE_LABEL[r.phase]}
              </span>
              <span className={styles.meta}>
                {r.id}, {r.done ? 'finished' : `${PHASE_LABEL[r.phase]} due week ${r.dueWeek + 1}`}
                {!r.done && r.remainingHours > 0 ? `, ${r.remainingHours}h left` : ''}
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
