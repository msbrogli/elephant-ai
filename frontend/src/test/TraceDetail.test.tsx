import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TraceDetail from '../pages/TraceDetail'

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
  mockFetch.mockReset()
})

const sampleTrace = {
  trace_id: 'abc12345deadbeef',
  database_name: 'family',
  message_id: 'msg-001',
  sender: '12345',
  message_text: 'We went to the park today with the kids',
  started_at: '2026-03-01T12:00:00Z',
  finished_at: '2026-03-01T12:00:03Z',
  intent: 'NEW_MEMORY',
  final_response: 'Got it! I logged that memory.',
  error: null,
  steps: [
    {
      step_type: 'intent',
      timestamp: '2026-03-01T12:00:00Z',
      resolved_intent: 'NEW_MEMORY',
      message_text: 'We went to the park today',
      sender: '12345',
    },
    {
      step_type: 'llm_call',
      timestamp: '2026-03-01T12:00:01Z',
      method: 'chat_with_tools',
      model: 'gpt-4o-mini',
      temperature: 0.7,
      max_tokens: 1024,
      messages: [{ role: 'system', content: 'You are...' }],
      response_content: null,
      response_tool_calls: [{ id: 'tc-1', function_name: 'create_memory', arguments: '{}' }],
      usage: { prompt_tokens: 500, completion_tokens: 50 },
    },
    {
      step_type: 'tool_exec',
      timestamp: '2026-03-01T12:00:02Z',
      tool_call_id: 'tc-1',
      function_name: 'create_memory',
      arguments: '{"title":"Park visit"}',
      result: '{"status":"created"}',
    },
    {
      step_type: 'git_commit',
      timestamp: '2026-03-01T12:00:02.5Z',
      sha: 'abcdef1234567890',
      message: '[memory] Park visit',
    },
  ],
}

function renderWithRoute(dbName: string, traceId: string) {
  return render(
    <MemoryRouter initialEntries={[`/${dbName}/${traceId}`]}>
      <Routes>
        <Route path="/:dbName/:traceId" element={<TraceDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TraceDetail', () => {
  it('renders trace metadata and steps', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(sampleTrace),
    })

    renderWithRoute('family', 'abc12345deadbeef')

    await waitFor(() => {
      expect(screen.getByText('Trace Detail')).toBeInTheDocument()
      expect(screen.getByText('abc12345deadbeef')).toBeInTheDocument()
      expect(screen.getByText('msg-001')).toBeInTheDocument()
    })

    expect(screen.getByText('We went to the park today with the kids')).toBeInTheDocument()
    expect(screen.getByText('Got it! I logged that memory.')).toBeInTheDocument()
    expect(screen.getByText('Steps (4)')).toBeInTheDocument()
  })

  it('shows all step type badges', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(sampleTrace),
    })

    renderWithRoute('family', 'abc12345deadbeef')

    await waitFor(() => {
      // "Intent" appears in both meta-grid label and step badge
      expect(screen.getAllByText('Intent').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('LLM Call')).toBeInTheDocument()
      expect(screen.getByText('Tool Exec')).toBeInTheDocument()
      expect(screen.getByText('Git Commit')).toBeInTheDocument()
    })
  })

  it('expands step cards on click', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(sampleTrace),
    })

    renderWithRoute('family', 'abc12345deadbeef')

    await waitFor(() => {
      expect(screen.getByText('LLM Call')).toBeInTheDocument()
    })

    // Click to expand the LLM Call step (second step, index 1)
    const headers = screen.getAllByText(/LLM Call|Tool Exec|Git Commit|Intent/)
    const llmHeader = headers.find(el => el.textContent === 'LLM Call')!
    fireEvent.click(llmHeader.closest('.step-header')!)

    await waitFor(() => {
      expect(screen.getByText(/gpt-4o-mini/)).toBeInTheDocument()
    })
  })

  it('shows error card when trace has error', async () => {
    const errorTrace = { ...sampleTrace, error: 'ValueError: something broke' }
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve(errorTrace),
    })

    renderWithRoute('family', 'abc12345deadbeef')

    await waitFor(() => {
      expect(screen.getByText('ValueError: something broke')).toBeInTheDocument()
    })
  })

  it('shows not found when trace missing', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ error: 'trace not found' }),
    })

    renderWithRoute('family', 'nonexistent')

    await waitFor(() => {
      expect(screen.getByText('Trace not found.')).toBeInTheDocument()
    })
  })
})
