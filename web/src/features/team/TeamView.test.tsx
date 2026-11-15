import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Team } from '../../shared/types.ts'
import { TeamView } from './TeamView.tsx'

afterEach(() => vi.restoreAllMocks())

const team: Team = {
  week: 30, target: 0.82, hotLoad: 0.9, warnings: ['e-014 build: weak match for f-builder-03'],
  people: [{
    id: 'f-builder-01', name: 'Lena Brandt', profile: 'builder', skills: ['german', 'airgap'], capacityHours: 40,
    plannedHours: 32, load: 0.8, hotStreak: 0, work: [{ engagementId: 'e-014', phase: 'build', hours: 32 }],
  }],
}

describe('TeamView', () => {
  it('shows each person with their planned hours', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(team)))
    render(<TeamView />)
    expect(await screen.findByText('Lena Brandt')).toBeTruthy()
    expect(screen.getByLabelText('32 of 40 hours')).toBeTruthy()
  })

  it('says how to recover when the team does not load', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ error: 'The plan store is down.' }), { status: 503 }))
    render(<TeamView />)
    expect(await screen.findByText(/The plan store is down/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('says when there is no one to plan', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ...team, people: [] })))
    render(<TeamView />)
    expect(await screen.findByText('No one on the team yet.')).toBeTruthy()
  })
})
