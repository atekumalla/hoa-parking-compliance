import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api, HistoryEntry, HistoryGroup, HistoryOptions } from '../api'
import EmptyState from '../components/EmptyState'
import ConfirmDeleteModal from '../components/ConfirmDeleteModal'

export default function VehicleHistoryPage() {
  const location = useLocation()
  const [options, setOptions] = useState<HistoryOptions | null>(null)
  const [plate, setPlate] = useState('')
  const [tag, setTag] = useState('')
  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [date, setDate] = useState('')
  const [groups, setGroups] = useState<HistoryGroup[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [exportMsg, setExportMsg] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<{ plate: string; entry: HistoryEntry } | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  useEffect(() => {
    api.historyOptions().then(setOptions).catch(() => {})
    const state = location.state as { prefillPlate?: string; prefillTag?: string } | null
    if (state?.prefillPlate) {
      setPlate(state.prefillPlate)
      void search({ plate: state.prefillPlate })
    } else if (state?.prefillTag) {
      setTag(state.prefillTag)
      void search({ tag: state.prefillTag })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function search(overrides?: Partial<{ plate: string; tag: string; make: string; model: string; date: string }>) {
    const params: Record<string, string> = {}
    const p = overrides?.plate ?? plate
    const t = overrides?.tag ?? tag
    const mk = overrides?.make ?? make
    const md = overrides?.model ?? model
    const d = overrides?.date ?? date
    if (p) params.plate = p
    if (t) params.tag = t
    if (mk) params.make = mk
    if (md) params.model = md
    if (d) params.date = d
    if (Object.keys(params).length === 0) {
      setSearchError('Please enter at least one search field or select a date.')
      return
    }
    setSearchError(null)
    setSearching(true)
    try {
      const result = await api.historySearch(params)
      setGroups(result.groups)
    } catch (e) {
      setSearchError((e as Error).message)
    } finally {
      setSearching(false)
    }
  }

  async function confirmDeleteEntry() {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await api.deleteEntry(pendingDelete.entry.timestamp, pendingDelete.plate, pendingDelete.entry.photo_url)
      setPendingDelete(null)
      void search()
    } catch (e) {
      setSearchError('Failed to delete: ' + (e as Error).message)
      setPendingDelete(null)
    } finally {
      setDeleting(false)
    }
  }

  async function exportPhotos(g: HistoryGroup) {
    setExportMsg(null)
    try {
      const result = await api.exportPhotos(g.license_plate, g.make, g.model)
      setExportMsg(`${result.message} — ${result.folder_url}`)
    } catch (e) {
      setExportMsg('Export failed: ' + (e as Error).message)
    }
  }

  return (
    <div>
      <div className="card">
        <span className="eyebrow">Lookup</span>
        <h2>Vehicle History</h2>
        <p>Search by plate, tag, make, model, or a specific date.</p>

        <div className="row">
          <div className="field">
            <label htmlFor="search-plate">License plate</label>
            <input id="search-plate" type="text" value={plate} onChange={(e) => setPlate(e.target.value)} list="plate-options" placeholder="Full or partial" />
            <datalist id="plate-options">{options?.plates.map((p) => <option key={p} value={p} />)}</datalist>
          </div>
          <div className="field">
            <label htmlFor="search-tag">Tag number</label>
            <input id="search-tag" type="text" value={tag} onChange={(e) => setTag(e.target.value)} list="tag-options" />
            <datalist id="tag-options">{options?.tags.map((t) => <option key={t} value={t} />)}</datalist>
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label htmlFor="search-make">Make</label>
            <input id="search-make" type="text" value={make} onChange={(e) => setMake(e.target.value)} list="make-options" />
            <datalist id="make-options">{options?.makes.map((m) => <option key={m} value={m} />)}</datalist>
          </div>
          <div className="field">
            <label htmlFor="search-model">Model</label>
            <input id="search-model" type="text" value={model} onChange={(e) => setModel(e.target.value)} list="model-options" />
            <datalist id="model-options">{options?.models.map((m) => <option key={m} value={m} />)}</datalist>
          </div>
        </div>
        <div className="field">
          <label htmlFor="search-date">Date logged</label>
          <input id="search-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        {searchError && <div className="alert warning">{searchError}</div>}

        <div className="row">
          <button className="btn" onClick={() => search()} disabled={searching}>{searching ? 'Searching…' : 'Search'}</button>
          <button className="btn secondary" onClick={() => { setPlate(''); setTag(''); setMake(''); setModel(''); setDate(''); setGroups(null); setSearchError(null) }}>Clear</button>
        </div>
      </div>

      {exportMsg && <div className="alert info">{exportMsg}</div>}

      {groups && groups.length === 0 && (
        <EmptyState title="No records match your search.">
          <p style={{ marginBottom: 0 }}>Try a partial plate, tag, or widen the date filter.</p>
        </EmptyState>
      )}

      {groups?.map((g) => (
        <div className="card" key={g.license_plate}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <h3 style={{ marginBottom: 0 }}><span className="plate">{g.license_plate}</span></h3>
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)' }}>
              {g.total_entries} entries &middot; {g.total_warnings} warnings &middot; {g.total_tows} tows
            </span>
          </div>
          <table>
            <thead><tr><th>Date / Time</th><th>Tag</th><th>Make / Model</th><th>Warned</th><th>Towed</th><th>Photo</th><th aria-hidden="true"></th></tr></thead>
            <tbody>
              {g.entries.map((e) => (
                <tr key={e.timestamp}>
                  <td>{new Date(e.timestamp).toLocaleString()}</td>
                  <td>{e.tag_number}</td>
                  <td>{e.make} {e.model}</td>
                  <td>{e.warned === 'Y' ? `Yes (${e.warned_date})` : 'No'}</td>
                  <td>{e.towed === 'Y' ? `Yes (${e.towed_date})` : 'No'}</td>
                  <td>{e.photo_url && <a href={e.photo_url} target="_blank" rel="noreferrer">View</a>}</td>
                  <td>
                    <button
                      className="btn danger"
                      aria-label={`Delete entry for ${g.license_plate} at ${new Date(e.timestamp).toLocaleString()}`}
                      onClick={() => setPendingDelete({ plate: g.license_plate, entry: e })}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {g.entries.some((e) => e.photo_url) && (
            <button className="btn secondary" style={{ marginTop: 'var(--space-3)' }} onClick={() => exportPhotos(g)}>Export photos to Drive</button>
          )}
        </div>
      ))}

      {pendingDelete && (
        <ConfirmDeleteModal
          title={`Delete entry for ${pendingDelete.plate}?`}
          busy={deleting}
          onConfirm={confirmDeleteEntry}
          onCancel={() => setPendingDelete(null)}
          fields={[
            { label: 'Plate', value: pendingDelete.plate },
            { label: 'Tag', value: pendingDelete.entry.tag_number },
            { label: 'Make / Model', value: `${pendingDelete.entry.make} ${pendingDelete.entry.model}`.trim() || 'N/A' },
            { label: 'Date / Time', value: new Date(pendingDelete.entry.timestamp).toLocaleString() },
            { label: 'Warned', value: pendingDelete.entry.warned === 'Y' ? `Yes (${pendingDelete.entry.warned_date})` : 'No' },
            { label: 'Towed', value: pendingDelete.entry.towed === 'Y' ? `Yes (${pendingDelete.entry.towed_date})` : 'No' },
            { label: 'Photo', value: pendingDelete.entry.photo_url ? <a href={pendingDelete.entry.photo_url} target="_blank" rel="noreferrer">View photo</a> : 'None' },
          ]}
        />
      )}
    </div>
  )
}
