import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ResultsView } from './ResultsView.tsx'

afterEach(() => vi.restoreAllMocks())

const score = (label: string, onPlan: number) => ({
  label, milestonesOnPlan: onPlan, surpriseSlips: 3, customerEscalations: 1, utilization: 0.72, burnoutWeeks: 10,
  marginShare: 0.09, productionIncidents: 0, engagementsDeclined: 2,
})

describe('ResultsView', () => {
  it('compares the engine with planning by hand', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      dev: { world: { name: 'dev', engagements: 52, people: 14, weeks: 52 }, designs: { engine: score('Delivery engine', 0.82), by_hand: score('By hand', 0.14) } },
      heldout: null,
    })))
    render(<ResultsView />)
    expect(await screen.findByText('Delivery engine')).toBeTruthy()
    expect(screen.getByText('By hand')).toBeTruthy()
  })

  it('says how to produce a report when there is none', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ dev: null, heldout: null })))
    render(<ResultsView />)
    expect(await screen.findByText('No report yet.')).toBeTruthy()
  })
})
