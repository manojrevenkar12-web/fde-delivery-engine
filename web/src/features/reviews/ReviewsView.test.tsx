import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReviewsView } from './ReviewsView.tsx'

afterEach(() => vi.restoreAllMocks())

const review = {
  engagementId: 'e-022', topology: 'air_gapped', documents: 18, goldenQuestions: 30, result: null,
  config: { split_length: 12, split_overlap: 0, top_k: 1, department_filter: null, generator_endpoint: 'local', replicas: 2 },
}

describe('ReviewsView', () => {
  it('runs a review and shows the recall it measured', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ reviews: [review] })))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({
      passed: false, recall: 0.43, grounded: 0.4, questions: 30, findings: ['top_k is 1, below 3'], misses: [],
    })))
    render(<ReviewsView />)
    fireEvent.click(await screen.findByRole('button', { name: /Run/ }))
    expect(await screen.findByText(/43/)).toBeTruthy()
    expect(screen.getByText('top_k is 1, below 3')).toBeTruthy()
  })

  it('says when nothing is waiting', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ reviews: [] })))
    render(<ReviewsView />)
    expect(await screen.findByText('Nothing waiting for review.')).toBeTruthy()
  })
})
