import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import StepCard from '../components/StepCard'

describe('StepCard', () => {
  it('renders collapsed by default', () => {
    const step = {
      step_type: 'intent',
      timestamp: '2026-03-01T12:00:00Z',
      resolved_intent: 'NEW_MEMORY',
      sender: '12345',
    }
    render(<StepCard step={step} index={0} />)
    expect(screen.getByText('Intent')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    // Body should not be visible
    expect(screen.queryByText('NEW_MEMORY')).not.toBeInTheDocument()
  })

  it('expands on click to show intent details', () => {
    const step = {
      step_type: 'intent',
      timestamp: '2026-03-01T12:00:00Z',
      resolved_intent: 'NEW_MEMORY',
      message_text: 'We went hiking',
      sender: '12345',
    }
    render(<StepCard step={step} index={0} />)
    fireEvent.click(screen.getByText('Intent').closest('.step-header')!)
    expect(screen.getByText(/NEW_MEMORY/)).toBeInTheDocument()
    expect(screen.getByText(/We went hiking/)).toBeInTheDocument()
  })

  it('renders LLM call with model and usage', () => {
    const step = {
      step_type: 'llm_call',
      timestamp: '2026-03-01T12:00:01Z',
      method: 'chat_with_tools',
      model: 'gpt-4o-mini',
      temperature: 0.7,
      max_tokens: 1024,
      messages: [{ role: 'system', content: 'hello' }],
      response_content: 'Done!',
      response_tool_calls: [],
      usage: { prompt_tokens: 100, completion_tokens: 20 },
    }
    render(<StepCard step={step} index={1} />)
    fireEvent.click(screen.getByText('LLM Call').closest('.step-header')!)
    expect(screen.getByText(/gpt-4o-mini/)).toBeInTheDocument()
    expect(screen.getByText(/chat_with_tools/)).toBeInTheDocument()
    expect(screen.getByText(/100/)).toBeInTheDocument()
    expect(screen.getByText('Done!')).toBeInTheDocument()
  })

  it('renders tool exec with toggle buttons', () => {
    const step = {
      step_type: 'tool_exec',
      timestamp: '2026-03-01T12:00:02Z',
      tool_call_id: 'tc-1',
      function_name: 'create_memory',
      arguments: '{"title":"Test"}',
      result: '{"status":"ok"}',
    }
    render(<StepCard step={step} index={2} />)
    fireEvent.click(screen.getByText('Tool Exec').closest('.step-header')!)
    expect(screen.getByText(/create_memory/)).toBeInTheDocument()
    expect(screen.getByText('Show arguments')).toBeInTheDocument()
    expect(screen.getByText('Show result')).toBeInTheDocument()

    // Toggle arguments
    fireEvent.click(screen.getByText('Show arguments'))
    expect(screen.getByText('Hide arguments')).toBeInTheDocument()
    expect(screen.getByText(/"title": "Test"/)).toBeInTheDocument()
  })

  it('renders git commit step with sha and message', () => {
    const step = {
      step_type: 'git_commit',
      timestamp: '2026-03-01T12:00:03Z',
      sha: 'abcdef1234567890',
      message: '[memory] Park outing',
    }
    render(<StepCard step={step} index={3} dbName="family" />)
    fireEvent.click(screen.getByText('Git Commit').closest('.step-header')!)
    expect(screen.getByText('abcdef12')).toBeInTheDocument()
    expect(screen.getByText('[memory] Park outing')).toBeInTheDocument()
    expect(screen.getByText('Show full diff')).toBeInTheDocument()
  })
})
