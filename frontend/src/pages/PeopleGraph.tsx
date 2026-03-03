import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import FamilyTree from '../components/FamilyTree'

// --- API types matching backend models ---

export interface PersonRelationship {
  person_id: string
  label: string
}

export interface CurrentThread {
  topic: string
  latest_update: string
  last_mentioned_date: string
}

export interface Group {
  group_id: string
  display_name: string
  color: string | null
}

export interface Person {
  person_id: string
  display_name: string
  relationship: string[]
  birthday: string | null
  groups: string[]
  relationships: PersonRelationship[]
  notes: string | null
  current_threads: CurrentThread[]
}

export default function PeopleGraph() {
  const { dbName } = useParams<{ dbName: string }>()
  const [people, setPeople] = useState<Person[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Person | null>(null)

  useEffect(() => {
    Promise.all([
      fetch(`/api/people/${dbName}`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),
      fetch(`/api/groups/${dbName}`).then(r => {
        if (!r.ok) return { groups: [] }
        return r.json()
      }),
    ])
      .then(([peopleData, groupsData]) => {
        setPeople(peopleData.people || [])
        setGroups(groupsData.groups || [])
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [dbName])

  return (
    <div>
      <div className="nav">
        <Link to="/">Databases</Link>
        <span>/</span>
        <Link to={`/${dbName}`}>{dbName}</Link>
        <span>/</span>
        <strong>People</strong>
      </div>
      <h1>People &amp; Relationships</h1>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : error ? (
        <div className="loading">Error: {error}</div>
      ) : people.length === 0 ? (
        <p>No people found.</p>
      ) : (
        <div className="people-graph-container">
          <div className="people-tree-area">
            <FamilyTree
              people={people}
              groups={groups}
              selected={selected}
              onSelect={setSelected}
            />
          </div>

          <div className="people-detail-panel">
            {selected ? (
              <>
                <h2>{selected.display_name}</h2>
                <p className="meta-item">
                  <span className="label">Relationship</span><br />
                  {selected.relationship.join(', ')}
                </p>
                {selected.groups.length > 0 && (
                  <div className="group-badges">
                    {selected.groups.map(gid => {
                      const group = groups.find(g => g.group_id === gid)
                      return (
                        <span
                          key={gid}
                          className="badge badge-group"
                          style={group?.color ? { backgroundColor: group.color } : undefined}
                        >
                          {group?.display_name ?? gid}
                        </span>
                      )
                    })}
                  </div>
                )}
                {selected.birthday && (
                  <p className="meta-item">
                    <span className="label">Birthday</span><br />
                    {selected.birthday}
                  </p>
                )}
                {selected.notes && (
                  <p className="meta-item">
                    <span className="label">Notes</span><br />
                    {selected.notes}
                  </p>
                )}
                {selected.current_threads.length > 0 && (
                  <div>
                    <p className="meta-item"><span className="label">Current Threads</span></p>
                    {selected.current_threads.map((t, i) => (
                      <div key={i} className="thread-item">
                        <strong>{t.topic}</strong>
                        <p>{t.latest_update}</p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className="loading">Click a card to see details</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
