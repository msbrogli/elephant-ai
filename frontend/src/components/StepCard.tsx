import { useState } from 'react'

interface Step {
  step_type: string
  timestamp: string
  [key: string]: unknown
}

function badgeClass(type: string): string {
  switch (type) {
    case 'llm_call': return 'badge-llm'
    case 'tool_exec': return 'badge-tool'
    case 'git_commit': return 'badge-git'
    case 'intent': return 'badge-intent'
    default: return ''
  }
}

function stepLabel(type: string): string {
  switch (type) {
    case 'llm_call': return 'LLM Call'
    case 'tool_exec': return 'Tool Exec'
    case 'git_commit': return 'Git Commit'
    case 'intent': return 'Intent'
    default: return type
  }
}

function LLMCallBody({ step }: { step: Step }) {
  const [showMessages, setShowMessages] = useState(false)
  const messages = step.messages as Array<Record<string, unknown>> | undefined
  const usage = step.usage as Record<string, number> | undefined
  const toolCalls = step.response_tool_calls as Array<Record<string, unknown>> | undefined

  return (
    <div>
      <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
        <strong>Model:</strong> {String(step.model || '')}
        {' | '}
        <strong>Method:</strong> {String(step.method || '')}
        {usage && (
          <>
            {' | '}
            <strong>Tokens:</strong> {usage.prompt_tokens ?? '?'} / {usage.completion_tokens ?? '?'}
          </>
        )}
      </div>

      {step.response_content ? (
        <>
          <div style={{ fontSize: '0.8rem', color: '#555', marginBottom: '0.25rem' }}>Response:</div>
          <pre>{String(step.response_content)}</pre>
        </>
      ) : null}

      {toolCalls && toolCalls.length > 0 && (
        <>
          <div style={{ fontSize: '0.8rem', color: '#555', marginBottom: '0.25rem' }}>Tool calls:</div>
          <pre>{JSON.stringify(toolCalls, null, 2)}</pre>
        </>
      )}

      {messages && messages.length > 0 && (
        <>
          <button
            onClick={() => setShowMessages(!showMessages)}
            style={{ fontSize: '0.8rem', marginTop: '0.5rem', background: 'none', border: '1px solid #ccc', padding: '0.25rem 0.5rem', cursor: 'pointer', borderRadius: '4px' }}
          >
            {showMessages ? 'Hide' : 'Show'} messages ({messages.length})
          </button>
          {showMessages && <pre>{JSON.stringify(messages, null, 2)}</pre>}
        </>
      )}
    </div>
  )
}

function ToolExecBody({ step }: { step: Step }) {
  const [showArgs, setShowArgs] = useState(false)
  const [showResult, setShowResult] = useState(false)

  let argsFormatted = String(step.arguments || '')
  try { argsFormatted = JSON.stringify(JSON.parse(argsFormatted), null, 2) } catch { /* keep raw */ }

  let resultFormatted = String(step.result || '')
  try { resultFormatted = JSON.stringify(JSON.parse(resultFormatted), null, 2) } catch { /* keep raw */ }

  return (
    <div>
      <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
        <strong>Function:</strong> {String(step.function_name || '')}
        {' | '}
        <strong>ID:</strong> {String(step.tool_call_id || '')}
      </div>
      <button
        onClick={() => setShowArgs(!showArgs)}
        style={{ fontSize: '0.8rem', background: 'none', border: '1px solid #ccc', padding: '0.25rem 0.5rem', cursor: 'pointer', borderRadius: '4px', marginRight: '0.5rem' }}
      >
        {showArgs ? 'Hide' : 'Show'} arguments
      </button>
      <button
        onClick={() => setShowResult(!showResult)}
        style={{ fontSize: '0.8rem', background: 'none', border: '1px solid #ccc', padding: '0.25rem 0.5rem', cursor: 'pointer', borderRadius: '4px' }}
      >
        {showResult ? 'Hide' : 'Show'} result
      </button>
      {showArgs && <pre>{argsFormatted}</pre>}
      {showResult && <pre>{resultFormatted}</pre>}
    </div>
  )
}

function GitCommitBody({ step, dbName }: { step: Step; dbName?: string }) {
  const [stat, setStat] = useState<string | null>(null)
  const [diff, setDiff] = useState<string | null>(null)
  const [showDiff, setShowDiff] = useState(false)
  const sha = String(step.sha || '')

  const fetchGit = (mode: 'stat' | 'diff') => {
    if (!dbName || !sha) return Promise.resolve('')
    return fetch(`/api/git/${dbName}/${sha}?mode=${mode}`)
      .then(r => r.json())
      .then(data => String(data.output || data.error || ''))
      .catch(() => '(failed to load)')
  }

  const handleShowStat = () => {
    if (stat !== null) return
    fetchGit('stat').then(setStat)
  }

  const handleToggleDiff = () => {
    if (!showDiff && diff === null) {
      fetchGit('diff').then(d => { setDiff(d); setShowDiff(true) })
    } else {
      setShowDiff(!showDiff)
    }
  }

  // Auto-load stat on mount
  useState(() => { handleShowStat() })

  return (
    <div>
      <div style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
        <span className="badge badge-git" style={{ fontFamily: 'monospace' }}>
          {sha.slice(0, 8)}
        </span>
        {' '}
        {String(step.message || '')}
      </div>
      {stat ? <pre>{stat}</pre> : null}
      <button
        onClick={handleToggleDiff}
        style={{ fontSize: '0.8rem', background: 'none', border: '1px solid #ccc', padding: '0.25rem 0.5rem', cursor: 'pointer', borderRadius: '4px', marginTop: '0.25rem' }}
      >
        {showDiff ? 'Hide' : 'Show'} full diff
      </button>
      {showDiff && diff ? <pre>{diff}</pre> : null}
    </div>
  )
}

function IntentBody({ step }: { step: Step }) {
  return (
    <div style={{ fontSize: '0.85rem' }}>
      <strong>Intent:</strong> {String(step.resolved_intent || '')}
      {' | '}
      <strong>Sender:</strong> {String(step.sender || '')}
      {step.message_text ? (
        <div style={{ marginTop: '0.25rem', color: '#555' }}>
          {String(step.message_text).slice(0, 200)}
        </div>
      ) : null}
    </div>
  )
}

export default function StepCard({ step, index, dbName }: { step: Step; index: number; dbName?: string }) {
  const [open, setOpen] = useState(false)

  const fmtTime = (iso: string) => {
    try { return new Date(iso).toLocaleTimeString() } catch { return iso }
  }

  return (
    <div className="step-card">
      <div className="step-header" onClick={() => setOpen(!open)}>
        <span style={{ fontSize: '0.75rem', color: '#888' }}>#{index + 1}</span>
        <span className={`badge ${badgeClass(step.step_type)}`}>{stepLabel(step.step_type)}</span>
        <span style={{ fontSize: '0.8rem', color: '#888', marginLeft: 'auto' }}>{fmtTime(step.timestamp)}</span>
        <span style={{ fontSize: '0.8rem' }}>{open ? '\u25BC' : '\u25B6'}</span>
      </div>
      {open && (
        <div className="step-body">
          {step.step_type === 'llm_call' && <LLMCallBody step={step} />}
          {step.step_type === 'tool_exec' && <ToolExecBody step={step} />}
          {step.step_type === 'git_commit' && <GitCommitBody step={step} dbName={dbName} />}
          {step.step_type === 'intent' && <IntentBody step={step} />}
        </div>
      )}
    </div>
  )
}
