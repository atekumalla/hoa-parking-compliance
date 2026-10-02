import { useEffect, useState } from 'react'
import { api, FolderInfo, StorageFile, StorageUsage } from '../api'
import EmptyState from '../components/EmptyState'
import Skeleton from '../components/Skeleton'

export default function StoragePage() {
  const [usage, setUsage] = useState<StorageUsage | null>(null)
  const [folders, setFolders] = useState<FolderInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedFolder, setSelectedFolder] = useState<FolderInfo | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [rangeFiles, setRangeFiles] = useState<StorageFile[] | null>(null)
  const [rangeTotalSize, setRangeTotalSize] = useState('')
  const [confirmRange, setConfirmRange] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  function load(refresh = false) {
    return Promise.all([api.storageUsage(refresh), api.storageFolders(refresh)]).then(([u, f]) => {
      setUsage(u)
      setFolders(f.folders)
      setError(null)
    }).catch((e) => setError((e as Error).message)).finally(() => setLoading(false))
  }

  async function deleteMonth() {
    if (!selectedFolder || confirmText.trim() !== selectedFolder.name) return
    setBusy(true)
    try {
      await api.deleteMonth(selectedFolder.id)
      setSelectedFolder(null)
      setConfirmText('')
      await load(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // Dates changed since the last search — clear stale results so the
  // "found files" list can never be deleted against mismatched dates.
  function updateStartDate(value: string) {
    setStartDate(value)
    setRangeFiles(null)
    setConfirmRange(false)
  }

  function updateEndDate(value: string) {
    setEndDate(value)
    setRangeFiles(null)
    setConfirmRange(false)
  }

  async function findRange() {
    if (!startDate || !endDate) return
    setError(null)
    try {
      const result = await api.storageRange(startDate, endDate)
      setRangeFiles(result.files)
      setRangeTotalSize(result.total_size_human)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function deleteRange() {
    if (!rangeFiles || !confirmRange) return
    setBusy(true)
    try {
      await api.deleteRange(rangeFiles.map((f) => f.id))
      setRangeFiles(null)
      setConfirmRange(false)
      await load(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <span className="eyebrow">Google Drive</span>
            <h2 style={{ marginBottom: 0 }}>Storage Management</h2>
          </div>
          <button className="btn secondary" onClick={() => load(true)}>Refresh Storage Info</button>
        </div>
        {error && <div className="alert error" style={{ marginTop: 'var(--space-3)' }}>{error}</div>}
        {usage && (
          <div className="row" style={{ marginTop: 'var(--space-4)' }}>
            <div className="field"><strong style={{ fontSize: 'var(--text-lg)' }}>{usage.file_count}</strong> photos stored</div>
            <div className="field"><strong style={{ fontSize: 'var(--text-lg)' }}>{usage.used_human}</strong> space used</div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Delete Photos by Month</h3>
        <p>Download or copy photos first &mdash; deletion is permanent.</p>
        {loading ? (
          <Skeleton rows={2} />
        ) : folders.length === 0 ? (
          <EmptyState title="No monthly folders yet." />
        ) : (
          <table>
            <thead><tr><th>Month</th><th>Photos</th><th>Size</th></tr></thead>
            <tbody>
              {folders.map((f) => (
                <tr key={f.id}><td>{f.name}</td><td>{f.file_count}</td><td>{f.total_size}</td></tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="field" style={{ marginTop: 'var(--space-4)' }}>
          <label htmlFor="month-select">Select month to delete</label>
          <select
            id="month-select"
            value={selectedFolder?.id ?? ''}
            onChange={(e) => setSelectedFolder(folders.find((f) => f.id === e.target.value) ?? null)}
          >
            <option value="">Choose a month&hellip;</option>
            {folders.filter((f) => f.file_count > 0).map((f) => (
              <option key={f.id} value={f.id}>{f.name} ({f.file_count} photos, {f.total_size})</option>
            ))}
          </select>
        </div>

        {selectedFolder && (
          <div>
            <div className="alert warning">
              This permanently deletes {selectedFolder.file_count} photos ({selectedFolder.total_size}) from {selectedFolder.name}. This cannot be undone.
            </div>
            <div className="field">
              <label htmlFor="confirm-month">Type <strong>{selectedFolder.name}</strong> to confirm</label>
              <input id="confirm-month" type="text" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
            </div>
            <button className="btn danger" disabled={busy || confirmText.trim() !== selectedFolder.name} onClick={deleteMonth}>
              Delete All Photos in Month
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Delete Photos by Date Range</h3>
        <div className="row">
          <div className="field"><label htmlFor="range-start">Start date</label><input id="range-start" type="date" value={startDate} onChange={(e) => updateStartDate(e.target.value)} /></div>
          <div className="field"><label htmlFor="range-end">End date</label><input id="range-end" type="date" value={endDate} onChange={(e) => updateEndDate(e.target.value)} /></div>
        </div>
        <button className="btn secondary" onClick={findRange}>Find Photos in Range</button>

        {rangeFiles && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <div className="alert info">Found {rangeFiles.length} photos ({rangeTotalSize}) between {startDate} and {endDate}.</div>
            <label className="check-row" style={{ textTransform: 'none', marginBottom: 'var(--space-3)' }}>
              <input type="checkbox" checked={confirmRange} onChange={(e) => setConfirmRange(e.target.checked)} />
              I confirm I want to delete these photos permanently
            </label>
            <button className="btn danger" disabled={!confirmRange || busy} onClick={deleteRange}>Delete Photos in Range</button>
          </div>
        )}
      </div>
    </div>
  )
}
