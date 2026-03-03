import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import StepCard from '../components/StepCard'

interface Step {
  step_type: string
  timestamp: string
  [key: string]: unknown
}

interface Trace {
  trace_id: string
  database_name: string
  message_id: string
  sender: string
  message_text: string
  started_at: string
  finished_at: string | null
  intent: string
  final_response: string
  steps: Step[]
  error: string | null
}

export default function TraceDetail() {
  const { dbName, traceId } = useParams<{ dbName: string; traceId: string }>()
  const [trace, setTrace] = useState<Trace | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/traces/${dbName}/${traceId}`)
      .then(r => r.json())
      .then(data => {
        if (data.trace_id) {
          setTrace(data)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [dbName, traceId])

  if (loading) return <div className="loading">Loading...</div>
  if (!trace) return <p>Trace not found.</p>

  const fmtTime = (iso: string | null) => {
    if (!iso) return '-'
    try { return new Date(iso).toLocaleString() } catch { return iso }
  }

  const durationMs = trace.finished_at && trace.started_at
    ? new Date(trace.finished_at).getTime() - new Date(trace.started_at).getTime()
    : null

  return (
    <div>
      <div className="nav">
        <Link to="/">Databases</Link>
        <span>/</span>
        <Link to={`/${dbName}`}>{dbName}</Link>
        <span>/</span>
        <strong>{trace.trace_id.slice(0, 8)}...</strong>
      </div>

      <h1>Trace Detail</h1>

      {trace.error && (
        <div className="card" style={{ borderColor: '#ef4444' }}>
          <span className="badge badge-error">Error</span>
          <pre style={{ margin: '0.5rem 0 0', whiteSpace: 'pre-wrap', color: '#991b1b' }}>
            {trace.error}
          </pre>
        </div>
      )}

      <div className="meta-grid">
        <div className="meta-item">
          <div className="label">Trace ID</div>
          <div>{trace.trace_id}</div>
        </div>
        <div className="meta-item">
          <div className="label">Message ID</div>
          <div>{trace.message_id}</div>
        </div>
        <div className="meta-item">
          <div className="label">Sender</div>
          <div>{trace.sender}</div>
        </div>
        <div className="meta-item">
          <div className="label">Intent</div>
          <div><span className="badge badge-intent">{trace.intent || 'unknown'}</span></div>
        </div>
        <div className="meta-item">
          <div className="label">Started</div>
          <div>{fmtTime(trace.started_at)}</div>
        </div>
        <div className="meta-item">
          <div className="label">Duration</div>
          <div>{durationMs !== null ? `${(durationMs / 1000).toFixed(2)}s` : '-'}</div>
        </div>
      </div>

      <div className="card">
        <h3>Message</h3>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0, background: 'transparent', color: 'inherit', padding: 0 }}>
          {trace.message_text}
        </pre>
      </div>

      {trace.final_response && (
        <div className="card">
          <h3>Response</h3>
          <pre style={{ whiteSpace: 'pre-wrap', margin: 0, background: 'transparent', color: 'inherit', padding: 0 }}>
            {trace.final_response}
          </pre>
        </div>
      )}

      <h2>Steps ({trace.steps.length})</h2>
      {trace.steps.map((step, i) => (
        <StepCard key={i} step={step} index={i} dbName={dbName} />
      ))}
    </div>
  )
}
