import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

interface Database {
  name: string
}

export default function DatabaseList() {
  const [databases, setDatabases] = useState<Database[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/traces/databases')
      .then(r => r.json())
      .then(data => setDatabases(data.databases || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Loading...</div>

  return (
    <div>
      <h1>Trace Viewer</h1>
      {databases.length === 0 ? (
        <p>No databases found.</p>
      ) : (
        databases.map(db => (
          <Link key={db.name} to={`/${db.name}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="card">
              <h3>{db.name}</h3>
              <p>View message processing traces</p>
            </div>
          </Link>
        ))
      )}
    </div>
  )
}
