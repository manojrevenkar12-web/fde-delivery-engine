import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { EngagementSummary } from '../../shared/types.ts'
import { EngagementList } from './EngagementList.tsx'

const row: EngagementSummary = {
  id: 'e-014', customer: 'Landesamt Nord', sector: 'public', topology: 'air_gapped', contract: 'fixed_fee',
  phase: 'build', done: false, dueWeek: 31, weeksLeft: 2, remainingHours: 64, plannedHours: 32,
  escalatedWeek: 29, risk: 3.5, riskReasons: ['blocker'], gate: null,
}

describe('EngagementList', () => {
  it('shows a skeleton while loading', () => {
    render(<EngagementList rows={undefined} loading error={undefined} onRetry={() => {}} selected={undefined} onSelect={() => {}} />)
    expect(screen.getByRole('status', { name: 'Loading engagements' })).toBeTruthy()
  })

  it('offers a retry when the list fails', () => {
    const retry = vi.fn()
    render(<EngagementList rows={undefined} loading={false} error="The server answered 503." onRetry={retry} selected={undefined} onSelect={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(retry).toHaveBeenCalledOnce()
  })

  it('says what to expect when there are no engagements', () => {
    render(<EngagementList rows={[]} loading={false} error={undefined} onRetry={() => {}} selected={undefined} onSelect={() => {}} />)
    expect(screen.getByText('No engagements yet.')).toBeTruthy()
  })

  it('marks an escalated engagement and selects it on click', () => {
    const select = vi.fn()
    render(<EngagementList rows={[row]} loading={false} error={undefined} onRetry={() => {}} selected={undefined} onSelect={select} />)
    expect(screen.getByText('Escalated')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Landesamt Nord/ }))
    expect(select).toHaveBeenCalledWith('e-014')
  })
})
