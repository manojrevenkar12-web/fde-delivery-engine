import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import { api } from '../../shared/api.ts'
import { kind, pct, signalTags } from '../../shared/format.ts'
import { PHASE_LABEL, SKILL_LABEL, motion as timing } from '../../shared/tokens.ts'
import type { Decision, EngagementDetail, Signals } from '../../shared/types.ts'
import { useResource } from '../../shared/useResource.ts'
import { EmptyState, ErrorState, Skeleton } from '../../shared/ui/States.tsx'
import styles from './Engagements.module.css'

function Phases({ e }: { e: EngagementDetail }) {
  return (
    <ol className={styles.phases} aria-label="Phases">
      {e.phases.map((p) => {
        const current = p.phase === e.phase && !e.done
        const share = Math.min(1, p.loggedHours / Math.max(1, p.scopedHours))
        return (
          <li key={p.phase} className={current ? styles.phaseNow : styles.phase}>
            <span className={styles.phaseName}>{PHASE_LABEL[p.phase]}</span>
            <span className={styles.track} aria-hidden="true">
              <span className={styles.logged} style={{ inlineSize: `${share * 100}%` }} />
            </span>
            <span className={styles.phaseMeta}>
              {p.loggedHours} of {p.scopedHours}h, due week {p.dueWeek + 1}
              {p.reportedDone !== null ? `, reported ${pct(p.reportedDone)}` : ''}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Verdict({ signals, decision }: { signals: Signals; decision: Decision }) {
  const still = useReducedMotion()
  const items = [...signalTags(signals), ...decision.reasons]
  return (
    <div className={decision.escalate ? styles.verdictUp : styles.verdict} role="status">
      <p className={styles.verdictHead}>
        {decision.escalate ? `Escalated: ${kind(decision.kind)}` : 'No escalation'}, risk {decision.score}
      </p>
      <ul className={styles.reasons}>
        {items.length === 0 ? <li>Nothing in this note moves the risk.</li> : null}
        {items.map((r, n) => (
          <motion.li
            key={r}
            initial={still ? false : { opacity: 0, y: timing.rise }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: n * timing.stagger, duration: timing.reveal, ease: timing.ease }}
          >
            {r}
          </motion.li>
        ))}
      </ul>
    </div>
  )
}

export function EngagementView({ id, onChanged }: { id: string | undefined; onChanged: () => void }) {
  const { data, error, loading, retry } = useResource<EngagementDetail | undefined>(
    () => (id ? api.engagement(id) : Promise.resolve(undefined)),
    [id],
  )
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [failure, setFailure] = useState<string>()
  const [last, setLast] = useState<{ signals: Signals; decision: Decision }>()

  if (!id) return <EmptyState title="Pick an engagement." hint="Its phases, the notes the team wrote and what the agent made of them open here." />
  if (loading && !data) return <Skeleton label="Loading the engagement" />
  if (error || !data) return <ErrorState what="The engagement" message={error ?? 'It was not found.'} onRetry={retry} />

  async function send() {
    setSending(true)
    setFailure(undefined)
    try {
      const out = await api.addNote(id!, draft.trim())
      setLast(out)
      setDraft('')
      await retry()
      onChanged()
    } catch (e) {
      setFailure(e instanceof Error ? e.message : String(e))
    } finally {
      setSending(false)
    }
  }

  const notes = [...data.notes].reverse()
  return (
    <section className={styles.view} aria-label={`Engagement ${data.id}`}>
      <header className={styles.head}>
        <h1 className={styles.title}>{data.customer}</h1>
        <p className={styles.sub}>
          {data.id}, {data.sector.replace('_', ' ')}, {data.topology.replace('_', '-')}, {data.contract === 'tm' ? 'time and materials' : 'fixed fee'}.
          {data.requiredSkills.length ? ` Needs ${data.requiredSkills.map((k) => SKILL_LABEL[k] ?? k).join(' and ')}.` : ''}
        </p>
      </header>
      <Phases e={data} />
      {!data.done ? (
        <form
          className={styles.compose}
          onSubmit={(e) => {
            e.preventDefault()
            void send()
          }}
        >
          <label htmlFor="note">This week's status note</label>
          <textarea id="note" rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Build is about 60% done. Still waiting for VPN access…" />
          <button type="submit" disabled={sending || draft.trim().length < 3}>
            {sending ? 'Reading…' : 'Read the note'}
          </button>
          {failure ? <p role="alert" className={styles.failure}>Not read: {failure}</p> : null}
        </form>
      ) : null}
      <AnimatePresence>{last ? <Verdict key={JSON.stringify(last)} signals={last.signals} decision={last.decision} /> : null}</AnimatePresence>
      <h2 className={styles.section}>Notes, newest first</h2>
      {notes.length === 0 ? (
        <EmptyState title="No notes yet." hint="The engagement lead's weekly note is what the agent reads." />
      ) : (
        <ol className={styles.notes}>
          {notes.map((n, i) => (
            <li key={`${n.week}-${i}`} className={styles.note}>
              <span className={styles.noteWeek}>Week {n.week + 1}</span>
              <p className={styles.noteText}>{n.text}</p>
              <span className={styles.tags}>
                {signalTags(n.signals).map((t) => (
                  <span key={t} className={styles.tag}>{t}</span>
                ))}
                {n.decision?.escalate ? <span className={styles.tagUp}>Escalated: {kind(n.decision.kind)}</span> : null}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
