import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DatabaseList from '../pages/DatabaseList'

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
  mockFetch.mockReset()
})

function renderWithRouter() {
  return render(
    <MemoryRouter>
      <DatabaseList />
    </MemoryRouter>,
  )
}

describe('DatabaseList', () => {
  it('shows loading then database cards', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ databases: [{ name: 'family' }, { name: 'work' }] }),
    })

    renderWithRouter()
    expect(screen.getByText('Loading...')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('family')).toBeInTheDocument()
      expect(screen.getByText('work')).toBeInTheDocument()
    })

    expect(mockFetch).toHaveBeenCalledWith('/api/traces/databases')
  })

  it('shows empty message when no databases', async () => {
    mockFetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ databases: [] }),
    })

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('No databases found.')).toBeInTheDocument()
    })
  })

  it('handles fetch error gracefully', async () => {
    mockFetch.mockRejectedValueOnce(new Error('network error'))

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('No databases found.')).toBeInTheDocument()
    })
  })
})
