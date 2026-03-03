import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import PeopleGraph from '../pages/PeopleGraph'
import { buildFamilyTree } from '../components/FamilyTree'
import type { Person } from '../pages/PeopleGraph'

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
  mockFetch.mockReset()
})

function renderWithRoute(dbName: string) {
  return render(
    <MemoryRouter initialEntries={[`/${dbName}/people`]}>
      <Routes>
        <Route path="/:dbName/people" element={<PeopleGraph />} />
      </Routes>
    </MemoryRouter>,
  )
}

const samplePeople: Person[] = [
  {
    person_id: 'marcelo',
    display_name: 'Marcelo',
    relationship: ['self'],
    birthday: '1985-01-01',
    groups: [],
    relationships: [],
    notes: null,
    current_threads: [],
  },
  {
    person_id: 'alice',
    display_name: 'Alice',
    relationship: ['sister'],
    birthday: '1990-05-15',
    groups: ['close-friends'],
    relationships: [],
    notes: 'Loves hiking',
    current_threads: [
      { topic: 'Trip', latest_update: 'Planning dates', last_mentioned_date: '2026-03-01' },
    ],
  },
  {
    person_id: 'bob',
    display_name: 'Bob',
    relationship: ['brother'],
    birthday: null,
    groups: [],
    relationships: [],
    notes: null,
    current_threads: [],
  },
]

function mockPeopleAndGroups(people = samplePeople, groups: object[] = []) {
  mockFetch
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ people }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ groups }),
    })
}

describe('PeopleGraph', () => {
  it('renders person cards for each person', async () => {
    mockPeopleAndGroups()

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('Marcelo')).toBeInTheDocument()
    })

    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
  })

  it('shows empty message when no people', async () => {
    mockPeopleAndGroups([], [])

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('No people found.')).toBeInTheDocument()
    })
  })

  it('shows error on fetch failure', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: 'fail' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ groups: [] }),
      })

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('Error: HTTP 500')).toBeInTheDocument()
    })
  })

  it('fetches correct API urls', async () => {
    mockPeopleAndGroups([], [])

    renderWithRoute('family')

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/people/family')
      expect(mockFetch).toHaveBeenCalledWith('/api/groups/family')
    })
  })

  it('shows detail panel when a card is clicked', async () => {
    mockPeopleAndGroups()

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Alice'))

    await waitFor(() => {
      // Detail panel shows name as h2
      expect(screen.getByRole('heading', { level: 2, name: 'Alice' })).toBeInTheDocument()
      expect(screen.getByText('Loves hiking')).toBeInTheDocument()
      expect(screen.getByText('Trip')).toBeInTheDocument()
    })
  })

  it('shows birthday on person cards', async () => {
    mockPeopleAndGroups()

    renderWithRoute('family')

    await waitFor(() => {
      expect(screen.getByText('1985-01-01')).toBeInTheDocument()
      expect(screen.getByText('1990-05-15')).toBeInTheDocument()
    })
  })
})

describe('buildFamilyTree', () => {
  const makePerson = (overrides: Partial<Person> & Pick<Person, 'person_id' | 'display_name' | 'relationship'>): Person => ({
    birthday: null,
    groups: [],
    relationships: [],
    notes: null,
    current_threads: [],
    ...overrides,
  })

  it('classifies self and spouse into core section', () => {
    const people = [
      makePerson({ person_id: 'me', display_name: 'Me', relationship: ['self'] }),
      makePerson({ person_id: 'pat', display_name: 'Pat', relationship: ['wife'] }),
    ]

    const sections = buildFamilyTree(people, [])
    const core = sections.find(s => s.key === 'core')

    expect(core).toBeDefined()
    expect(core!.people).toHaveLength(2)
    // Self should come first
    expect(core!.people[0].person_id).toBe('me')
    expect(core!.people[1].person_id).toBe('pat')
  })

  it('classifies parents, siblings, children, in-laws', () => {
    const people = [
      makePerson({ person_id: 'me', display_name: 'Me', relationship: ['self'] }),
      makePerson({ person_id: 'dad', display_name: 'Dad', relationship: ['father'] }),
      makePerson({ person_id: 'mom', display_name: 'Mom', relationship: ['mother'] }),
      makePerson({ person_id: 'sis', display_name: 'Sis', relationship: ['sister'] }),
      makePerson({ person_id: 'kid', display_name: 'Kid', relationship: ['son'] }),
      makePerson({ person_id: 'mil', display_name: 'MIL', relationship: ['mother-in-law'] }),
    ]

    const sections = buildFamilyTree(people, [])
    const keys = sections.map(s => s.key)

    expect(keys).toEqual(['parents', 'siblings', 'core', 'inlaws', 'children'])
    expect(sections.find(s => s.key === 'parents')!.people).toHaveLength(2)
    expect(sections.find(s => s.key === 'siblings')!.people).toHaveLength(1)
    expect(sections.find(s => s.key === 'core')!.people).toHaveLength(1)
    expect(sections.find(s => s.key === 'inlaws')!.people).toHaveLength(1)
    expect(sections.find(s => s.key === 'children')!.people).toHaveLength(1)
  })

  it('puts unknown relationships in other section', () => {
    const people = [
      makePerson({ person_id: 'joe', display_name: 'Joe', relationship: ['friend'] }),
    ]

    const sections = buildFamilyTree(people, [])

    expect(sections).toHaveLength(1)
    expect(sections[0].key).toBe('other')
    expect(sections[0].people[0].person_id).toBe('joe')
  })

  it('omits empty sections', () => {
    const people = [
      makePerson({ person_id: 'me', display_name: 'Me', relationship: ['self'] }),
    ]

    const sections = buildFamilyTree(people, [])

    expect(sections).toHaveLength(1)
    expect(sections[0].key).toBe('core')
  })

  it('husband is classified as core/spouse', () => {
    const people = [
      makePerson({ person_id: 'me', display_name: 'Me', relationship: ['self'] }),
      makePerson({ person_id: 'h', display_name: 'Husband', relationship: ['husband'] }),
    ]

    const sections = buildFamilyTree(people, [])
    const core = sections.find(s => s.key === 'core')

    expect(core!.people).toHaveLength(2)
  })
})
