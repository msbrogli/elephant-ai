import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TraceList from '../pages/TraceList'

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
  mockFetch.mockReset()
})

function renderWithRoute(dbName: string) {
  return render(
    <MemoryRouter initialEntries={[`/${dbName}`]}>
      <Routes>
        <Route path="/:dbName" element={<TraceList />} />
      </Routes>
    </MemoryRouter>,
  )
}

const sampleTraces = [
  {
    trace_id: 'abc123',
    started_at: '2026-03-01T12:00:00Z',
    intent: 'NEW_MEMORY',
    message_text: 'We went to the park today',
    sender: '12345',
    step_counts: { llm_call: 2, tool_exec: 1, intent: 1 },
    has_error: false,
  },
  {
    trace_id: 'def456',
    started_at: '2026-03-01T11:00:00Z',
    intent: 'DIGEST_FEEDBACK',
    message_text: 'Looks great!',
    sender: '12345',
    step_counts: { intent: 1 },
    has_error: true,
  },
]

describe('TraceList', () => {
  it('renders traces in a table', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ traces: sampleTraces, total: 2 }),
    })

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('We went to the park today')).toBeInTheDocument()
      expect(screen.getByText('Looks great!')).toBeInTheDocument()
    })

    expect(mockFetch).toHaveBeenCalledWith('/api/traces/family?page=0&per_page=30')
  })

  it('shows error badge for traces with errors', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ traces: sampleTraces, total: 2 }),
    })

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('error')).toBeInTheDocument()
    })
  })

  it('shows empty message when no traces', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ traces: [], total: 0 }),
    })

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('No traces yet.')).toBeInTheDocument()
    })
  })

  it('shows step count badges', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ traces: sampleTraces, total: 2 }),
    })

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('llm call (2)')).toBeInTheDocument()
      expect(screen.getByText('tool exec (1)')).toBeInTheDocument()
    })
  })
})
