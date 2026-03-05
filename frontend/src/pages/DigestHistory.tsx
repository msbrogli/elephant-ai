import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

interface DigestEntry {
  sent_at: string
  text: string
  memory_ids: string[]
  message_id: string | null
}

export default function DigestHistory() {
  const { dbName } = useParams<{ dbName: string }>()
  const [digests, setDigests] = useState<DigestEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)

  const perPage = 20

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    })

    fetch(`/api/digests/${dbName}?${params}`)
      .then(r => r.json())
      .then(data => {
        setDigests(data.digests || [])
        setTotal(data.total || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [dbName, page])

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div>
      <div className="nav">
        <Link to="/">Databases</Link>
        <span>/</span>
        <Link to={`/${dbName}`}>{dbName}</Link>
        <span>/</span>
        <strong>Digests</strong>
      </div>
      <h1>Digest History</h1>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : digests.length === 0 ? (
        <p>No digests sent yet.</p>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {digests.map((d, i) => (
              <div key={`${d.sent_at}-${i}`} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <strong>{formatDate(d.sent_at)}</strong>
                  {d.memory_ids.length > 0 && (
                    <span className="badge badge-intent">
                      {d.memory_ids.length} {d.memory_ids.length === 1 ? 'memory' : 'memories'}
                    </span>
                  )}
                </div>
                <p style={{ margin: '0.25rem 0', whiteSpace: 'pre-wrap' }}>{d.text}</p>
              </div>
            ))}
          </div>

          <div className="pagination">
            <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Prev</button>
            <span>Page {page + 1} of {Math.ceil(total / perPage)}</span>
            <button disabled={(page + 1) * perPage >= total} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        </>
      )}
    </div>
  )
}
