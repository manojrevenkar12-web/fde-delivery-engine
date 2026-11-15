import { motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import { api } from '../../shared/api.ts'
import { pct } from '../../shared/format.ts'
import { PHASE_LABEL, PROFILE_LABEL, motion as timing } from '../../shared/tokens.ts'
import type { Team } from '../../shared/types.ts'
import { useResource } from '../../shared/useResource.ts'
import { EmptyState, ErrorState, Skeleton } from '../../shared/ui/States.tsx'
import styles from './Team.module.css'

/** The week's staffing board: everyone's planned load against the target, and what they are on. */
export function TeamView() {
  const { data, setData, error, loading, retry } = useResource(() => api.team(), [])
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<string>()
  const still = useReducedMotion()

  async function replan() {
    setBusy(true)
    setFailure(undefined)
    try {
      setData(await api.replan())
    } catch (e) {
      setFailure(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (loading && !data) return <Skeleton label="Loading the team" />
  if (error || !data) return <ErrorState what="The team" message={error ?? 'Nothing came back.'} onRetry={retry} />
  const team: Team = data
  if (team.people.length === 0) return <EmptyState title="No one on the team yet." hint="Add people to the roster to plan a week." />
  const byProfile = ['advisory', 'builder', 'operating', 'support']
  return (
    <section className={styles.view} aria-label="Team">
      <header className={styles.head}>
        <div>
          <h1 className={styles.title}>Week {team.week + 1}</h1>
          <p className={styles.sub}>
            Target {pct(team.target)} of each person's week. Above {pct(team.hotLoad)} counts as a stretch week, and
            nobody gets two in a row.
          </p>
        </div>
        <button type="button" className={styles.replan} onClick={() => void replan()} disabled={busy}>
          {busy ? 'Planning…' : 'Plan the week again'}
        </button>
      </header>
      {failure ? <p role="alert" className={styles.failure}>Not planned: {failure}</p> : null}
      {byProfile.map((profile) => (
        <div key={profile} className={styles.group}>
          <h2 className={styles.profile}>{PROFILE_LABEL[profile]}</h2>
          <ul className={styles.people}>
            {team.people.filter((p) => p.profile === profile).map((p) => (
              <li key={p.id} className={styles.person}>
                <span className={styles.name}>
                  {p.name} <span className={styles.id}>{p.id}</span>
                </span>
                <span className={styles.bar} aria-label={`${p.plannedHours} of ${p.capacityHours} hours`}>
                  <motion.span
                    className={p.load > team.hotLoad ? styles.fillHot : styles.fill}
                    initial={still ? false : { inlineSize: 0 }}
                    animate={{ inlineSize: `${Math.min(1, p.load) * 100}%` }}
                    transition={{ duration: timing.reveal, ease: timing.ease }}
                  />
                  <span className={styles.target} style={{ insetInlineStart: `${team.target * 100}%` }} />
                </span>
                <span className={styles.hours}>
                  {p.plannedHours}/{p.capacityHours}h{p.hotStreak > 0 ? ', stretched' : ''}
                </span>
                <span className={styles.work}>
                  {p.work.length === 0
                    ? 'Free this week'
                    : p.work
                        .map((w) => (w.engagementId.startsWith('template:') ? `template ${w.engagementId.slice(9).replace(/_/g, ' ')}` : `${w.engagementId} ${PHASE_LABEL[w.phase]}`) + ` ${w.hours}h`)
                        .join(', ')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {team.warnings.length > 0 ? (
        <div className={styles.warnings}>
          <h2 className={styles.profile}>Short this week</h2>
          <ul>
            {team.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
