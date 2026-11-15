import { layout } from '../tokens.ts'
import styles from './States.module.css'

export function Skeleton({ label, lines = layout.skeletonRows }: { label: string; lines?: number }) {
  return (
    <div className={styles.skeleton} role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, n) => (
        <span key={n} className={styles.line} style={{ inlineSize: layout.skeletonWidths[n % layout.skeletonWidths.length] }} />
      ))}
    </div>
  )
}

export function ErrorState({ what, message, onRetry }: { what: string; message: string; onRetry: () => void }) {
  return (
    <div className={styles.error} role="alert">
      <p>
        <strong>{what} did not load.</strong> {message}
      </p>
      <button type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className={styles.empty}>
      <p className={styles.title}>{title}</p>
      <p>{hint}</p>
    </div>
  )
}
