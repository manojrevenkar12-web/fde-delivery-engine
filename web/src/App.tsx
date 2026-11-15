import { useState } from 'react'
import { EngagementList } from './features/engagements/EngagementList.tsx'
import { EngagementView } from './features/engagements/EngagementView.tsx'
import listStyles from './features/engagements/Engagements.module.css'
import { ResultsView } from './features/results/ResultsView.tsx'
import { ReviewsView } from './features/reviews/ReviewsView.tsx'
import { TeamView } from './features/team/TeamView.tsx'
import { api } from './shared/api.ts'
import { useResource } from './shared/useResource.ts'
import styles from './App.module.css'

type View = 'engagements' | 'team' | 'reviews' | 'results'
const VIEWS: { id: View; label: string }[] = [
  { id: 'engagements', label: 'Engagements' },
  { id: 'team', label: 'Team' },
  { id: 'reviews', label: 'Go-live reviews' },
  { id: 'results', label: 'Results' },
]

export function App() {
  const [view, setView] = useState<View>('engagements')
  const [selected, setSelected] = useState<string>()
  const list = useResource(() => api.engagements(), [])
  return (
    <div className={styles.app}>
      <header className={styles.bar}>
        <p className={styles.brand}>Delivery desk</p>
        <nav aria-label="Views" className={styles.views}>
          {VIEWS.map((v) => (
            <button key={v.id} type="button" aria-pressed={view === v.id} onClick={() => setView(v.id)}>
              {v.label}
            </button>
          ))}
        </nav>
      </header>
      <main className={styles.main}>
        {view === 'engagements' ? (
          <div className={listStyles.layout}>
            <div className={listStyles.listPane}>
              <EngagementList
                rows={list.data?.engagements}
                loading={list.loading}
                error={list.error}
                onRetry={list.retry}
                selected={selected}
                onSelect={setSelected}
              />
            </div>
            <div className={listStyles.detailPane}>
              <EngagementView id={selected} onChanged={() => void list.retry()} />
            </div>
          </div>
        ) : null}
        {view === 'team' ? <TeamView /> : null}
        {view === 'reviews' ? <ReviewsView /> : null}
        {view === 'results' ? <ResultsView /> : null}
      </main>
    </div>
  )
}
