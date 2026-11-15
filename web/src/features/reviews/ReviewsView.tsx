import { motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import { api } from '../../shared/api.ts'
import { pct } from '../../shared/format.ts'
import { motion as timing } from '../../shared/tokens.ts'
import type { GateResult, Review } from '../../shared/types.ts'
import { useResource } from '../../shared/useResource.ts'
import { EmptyState, ErrorState, Skeleton } from '../../shared/ui/States.tsx'
import styles from './Reviews.module.css'

function Result({ r }: { r: GateResult }) {
  const still = useReducedMotion()
  return (
    <motion.div
      className={r.passed ? styles.pass : styles.block}
      initial={still ? false : { opacity: 0, y: timing.rise }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: timing.reveal, ease: timing.ease }}
      role="status"
    >
      <p className={styles.verdict}>{r.passed ? 'Ready to go live' : 'Blocked before go-live'}</p>
      <dl className={styles.figures}>
        <div>
          <dt>Recall on {r.questions} golden questions</dt>
          <dd>{pct(r.recall)}</dd>
        </div>
        <div>
          <dt>Answers grounded in the right document</dt>
          <dd>{pct(r.grounded)}</dd>
        </div>
      </dl>
      {r.findings.length > 0 ? (
        <ul className={styles.findings}>
          {r.findings.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      ) : null}
      {r.misses.length > 0 ? (
        <details>
          <summary>Questions it missed</summary>
          <ul>
            {r.misses.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </motion.div>
  )
}

function ReviewCard({ review }: { review: Review }) {
  const [result, setResult] = useState<GateResult | null>(review.result)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<string>()
  async function run() {
    setBusy(true)
    setFailure(undefined)
    try {
      setResult(await api.runReview(review.engagementId))
    } catch (e) {
      setFailure(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <li className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.eid}>{review.engagementId}</h2>
        <span className={styles.topology}>{review.topology.replace('_', '-')}</span>
      </div>
      <p className={styles.meta}>
        {review.documents} documents indexed, {review.goldenQuestions} golden questions from the customer.
      </p>
      <pre className={styles.config}>{JSON.stringify(review.config, null, 2)}</pre>
      <button type="button" className={styles.run} onClick={() => void run()} disabled={busy}>
        {busy ? 'Running the pipeline…' : result ? 'Run the review again' : 'Run the go-live review'}
      </button>
      {failure ? <p role="alert" className={styles.failure}>The review did not run: {failure}</p> : null}
      {result ? <Result r={result} /> : null}
    </li>
  )
}

/** Pipelines at the end of build: run the customer's golden questions through the real pipeline before go-live. */
export function ReviewsView() {
  const { data, error, loading, retry } = useResource(() => api.reviews(), [])
  return (
    <section className={styles.view} aria-label="Go-live reviews">
      <h1 className={styles.title}>Go-live reviews</h1>
      <p className={styles.sub}>
        Each pipeline runs as deployed: documents split and indexed as configured, retrieved with BM25, answered from
        what was retrieved. It goes live only above the bar and inside its topology.
      </p>
      {loading && !data ? <Skeleton label="Loading reviews" /> : null}
      {error ? <ErrorState what="The reviews" message={error} onRetry={retry} /> : null}
      {data && data.reviews.length === 0 ? (
        <EmptyState title="Nothing waiting for review." hint="Pipelines arrive here when a build phase ends." />
      ) : null}
      {data && data.reviews.length > 0 ? (
        <ul className={styles.cards}>
          {data.reviews.map((r) => (
            <ReviewCard key={r.engagementId} review={r} />
          ))}
        </ul>
      ) : null}
    </section>
  )
}
