import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, ApiError, KnownVehicle, TodayEntry, ViolationStatus } from '../api'
import CameraCapture from '../components/CameraCapture'
import CollapsibleSection from '../components/CollapsibleSection'
import ConfirmDeleteModal from '../components/ConfirmDeleteModal'
import EmptyState from '../components/EmptyState'
import Skeleton from '../components/Skeleton'

interface PrefillState {
  license_plate?: string
  tag_number?: string
  make?: string
  model?: string
}

export default function AddVehiclePage() {
  const location = useLocation()

  const [todayEntries, setTodayEntries] = useState<TodayEntry[]>([])
  const [todayLoading, setTodayLoading] = useState(true)
  const [todayRefreshing, setTodayRefreshing] = useState(false)
  const [sortKey, setSortKey] = useState<'time' | 'days_30'>('time')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [knownVehicles, setKnownVehicles] = useState<KnownVehicle[]>([])

  const [licensePlate, setLicensePlate] = useState('')
  const [tagNumber, setTagNumber] = useState('')
  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [warned, setWarned] = useState(false)
  const [towed, setTowed] = useState(false)

  const [photoSource, setPhotoSource] = useState<'none' | 'camera' | 'upload'>('none')
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [addWatermark, setAddWatermark] = useState(false)
  const [useExifDate, setUseExifDate] = useState(true)

  // Revoke the object URL whenever it's replaced or the page is left, so
  // attaching/removing many photos in one session doesn't leak blob memory.
  useEffect(() => {
    return () => {
      if (photoPreview) URL.revokeObjectURL(photoPreview)
    }
  }, [photoPreview])

  const [violation, setViolation] = useState<ViolationStatus | null>(null)
  const [pendingDuplicate, setPendingDuplicate] = useState<{ time: string } | null>(null)
  const [pendingDelete, setPendingDelete] = useState<TodayEntry | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ kind: 'error' | 'success' | 'info'; text: string } | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => {
    void loadTodayEntries()
    api.knownVehicles().then((r) => setKnownVehicles(r.vehicles)).catch(() => {})

    const prefill = (location.state as { prefill?: PrefillState } | null)?.prefill
    if (prefill) {
      setLicensePlate(prefill.license_plate ?? '')
      setTagNumber(prefill.tag_number ?? '')
      setMake(prefill.make ?? '')
      setModel(prefill.model ?? '')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!licensePlate.trim()) {
      setViolation(null)
      return
    }
    let cancelled = false
    const t = setTimeout(() => {
      api.violationStatus(licensePlate).then((v) => {
        if (!cancelled) setViolation(v)
      }).catch(() => {
        if (!cancelled) setViolation(null)
      })
    }, 300)
    // Guards against out-of-order responses: if the plate changes again
    // before this request resolves, its (now-stale) result is dropped.
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [licensePlate])

  function loadTodayEntries() {
    return api.todayEntries().then((r) => setTodayEntries(r.entries)).finally(() => setTodayLoading(false))
  }

  async function refreshTodayEntries() {
    setTodayRefreshing(true)
    try {
      await loadTodayEntries()
    } finally {
      setTodayRefreshing(false)
    }
  }

  function pickKnownVehicle(label: string) {
    const v = knownVehicles.find((k) => k.label === label)
    if (v) {
      setLicensePlate(v.license_plate)
      setTagNumber(v.tag_number)
      setMake(v.make)
      setModel(v.model)
    }
  }

  function onFileSelected(file: File) {
    setPhotoFile(file)
    setPhotoPreview(URL.createObjectURL(file))
  }

  function clearPhoto() {
    setPhotoFile(null)
    setPhotoPreview(null)
    setPhotoSource('none')
  }

  async function analyzePhoto() {
    if (!photoFile) return
    setAnalyzing(true)
    setMessage(null)
    try {
      const result = await api.analyzePhoto(photoFile)
      if (result.license_plate) setLicensePlate(result.license_plate)
      if (result.make) setMake(result.make)
      if (result.model) setModel(result.model)
      if (result.tag_number) setTagNumber(result.tag_number)
      const detected = [result.license_plate, result.make, result.model].filter(Boolean).join(' · ')
      setMessage({ kind: 'success', text: detected ? `AI detected: ${detected}` : 'AI could not identify this vehicle — enter details manually.' })
    } catch (e) {
      setMessage({ kind: 'error', text: 'Analysis failed: ' + (e as Error).message })
    } finally {
      setAnalyzing(false)
    }
  }

  async function submit(force = false) {
    if (!licensePlate.trim() || !tagNumber.trim()) {
      setMessage({ kind: 'error', text: 'Please fill in at least License Plate and Tag Number' })
      return
    }
    setSubmitting(true)
    setMessage(null)
    try {
      const form = new FormData()
      form.append('license_plate', licensePlate)
      form.append('tag_number', tagNumber)
      form.append('make', make)
      form.append('model', model)
      form.append('warned', String(warned))
      form.append('towed', String(towed))
      form.append('use_exif_date', String(photoSource === 'upload' && useExifDate))
      form.append('add_watermark', String(photoSource !== 'none' && addWatermark))
      form.append('force', String(force))
      if (photoFile) form.append('photo', photoFile)

      const result = await api.createEntry(form)
      setMessage({
        kind: result.photo_upload_warning ? 'info' : 'success',
        text: result.photo_upload_warning ?? `Entry saved for ${result.license_plate}.`,
      })
      resetForm()
      void loadTodayEntries()
      api.knownVehicles().then((r) => setKnownVehicles(r.vehicles)).catch(() => {})
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = e.detail as { duplicate_time?: string }
        setPendingDuplicate({ time: detail.duplicate_time ?? 'earlier today' })
      } else {
        setMessage({ kind: 'error', text: (e as Error).message })
      }
    } finally {
      setSubmitting(false)
    }
  }

  function resetForm() {
    setLicensePlate('')
    setTagNumber('')
    setMake('')
    setModel('')
    setWarned(false)
    setTowed(false)
    clearPhoto()
    setPendingDuplicate(null)
  }

  async function confirmDeleteTodayEntry() {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await api.deleteEntry(pendingDelete.timestamp, pendingDelete.license_plate, pendingDelete.photo_url)
      setPendingDelete(null)
      void loadTodayEntries()
    } catch (e) {
      setMessage({ kind: 'error', text: 'Failed to delete: ' + (e as Error).message })
      setPendingDelete(null)
    } finally {
      setDeleting(false)
    }
  }

  /**
   * Status stamp for a today's-entry row. Priority: an action already taken
   * on THIS sighting (Towed/Warned) always wins; otherwise falls back to the
   * vehicle's overall 30-day violation status (Can Be Towed/Can Be Warned).
   */
  function todayStatus(e: TodayEntry): { label: string; tone: 'ok' | 'warn' | 'danger' } {
    if (e.towed) return { label: 'Towed', tone: 'danger' }
    if (e.warned) return { label: 'Warned', tone: 'warn' }
    if (e.can_tow) return { label: 'Can Be Towed', tone: 'danger' }
    if (e.needs_warning) return { label: 'Can Be Warned', tone: 'warn' }
    return { label: 'Compliant', tone: 'ok' }
  }

  function toggleSort(key: 'time' | 'days_30') {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  function sortIndicator(key: 'time' | 'days_30') {
    if (sortKey !== key) return null
    return <span aria-hidden="true">{sortDir === 'asc' ? ' \u25b2' : ' \u25bc'}</span>
  }

  const sortedTodayEntries = useMemo(() => {
    const sorted = [...todayEntries]
    sorted.sort((a, b) => {
      const cmp = sortKey === 'time'
        ? new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        : a.days_30 - b.days_30
      return sortDir === 'asc' ? cmp : -cmp
    })
    return sorted
  }, [todayEntries, sortKey, sortDir])

  return (
    <div>
      <CollapsibleSection
        title={
          <>
            <span className="eyebrow">Today &middot; {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}</span>
            <h2 style={{ marginBottom: 0 }}>Entries Logged Today</h2>
          </>
        }
        actions={
          <button type="button" className="btn secondary" onClick={refreshTodayEntries} disabled={todayRefreshing}>
            {todayRefreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        }
      >
        {todayLoading ? (
          <Skeleton rows={3} />
        ) : todayEntries.length === 0 ? (
          <EmptyState title="No sightings logged yet today.">
            <p style={{ marginBottom: 0 }}>Entries you add below will show up here so you can spot duplicates at a glance.</p>
          </EmptyState>
        ) : (
          <table>
            <thead>
              <tr>
                <th aria-sort={sortKey === 'time' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  <button type="button" className="sort-btn" onClick={() => toggleSort('time')}>Time{sortIndicator('time')}</button>
                </th>
                <th>Plate</th>
                <th>Tag</th>
                <th>Make / Model</th>
                <th aria-sort={sortKey === 'days_30' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  <button type="button" className="sort-btn" onClick={() => toggleSort('days_30')}>Days (30d){sortIndicator('days_30')}</button>
                </th>
                <th>Status</th>
                <th aria-hidden="true"></th>
              </tr>
            </thead>
            <tbody>
              {sortedTodayEntries.map((e) => (
                <tr key={e.timestamp + e.license_plate}>
                  <td>{e.time}</td>
                  <td>
                    <Link className="plate" to="/history" state={{ prefillPlate: e.license_plate }} title={`View history for plate ${e.license_plate}`}>
                      {e.license_plate}
                    </Link>
                  </td>
                  <td>
                    <Link to="/history" state={{ prefillTag: e.tag_number }} title={`View history for tag ${e.tag_number}`}>
                      {e.tag_number}
                    </Link>
                  </td>
                  <td>{e.make} {e.model}</td>
                  <td>{e.days_30}</td>
                  <td>
                    <span className={`stamp ${todayStatus(e).tone}`}>{todayStatus(e).label}</span>
                  </td>
                  <td>
                    <button
                      className="btn danger"
                      aria-label={`Delete entry for plate ${e.license_plate} at ${e.time}`}
                      title="Delete entry"
                      onClick={() => setPendingDelete(e)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CollapsibleSection>

      <CollapsibleSection title={<h2 style={{ marginBottom: 0 }}>Add Vehicle Entry</h2>}>
        {knownVehicles.length > 0 && (
          <div className="field">
            <label htmlFor="known-vehicle">Quick select a known vehicle</label>
            <select id="known-vehicle" onChange={(e) => e.target.value && pickKnownVehicle(e.target.value)} defaultValue="">
              <option value="">Auto-fill from a previously seen vehicle&hellip;</option>
              {knownVehicles.map((v) => (
                <option key={v.label} value={v.label}>{v.label}</option>
              ))}
            </select>
          </div>
        )}

        <hr className="section-divider" />

        <div className="field">
          <label>Attach a photo</label>
          <div className="row">
            <button
              type="button"
              className={`btn secondary ${photoSource === 'camera' ? 'active' : ''}`}
              onClick={() => setPhotoSource('camera')}
            >
              Take Photo
            </button>
            <button
              type="button"
              className={`btn secondary ${photoSource === 'upload' ? 'active' : ''}`}
              onClick={() => setPhotoSource('upload')}
            >
              Upload File
            </button>
            {photoFile && <button type="button" className="btn secondary" onClick={clearPhoto}>Remove photo</button>}
          </div>
        </div>

        {photoSource === 'camera' && !photoFile && <CameraCapture onCapture={onFileSelected} />}
        {photoSource === 'upload' && !photoFile && (
          <input
            type="file"
            accept="image/*,.heic"
            aria-label="Upload a vehicle photo"
            onChange={(e) => e.target.files?.[0] && onFileSelected(e.target.files[0])}
          />
        )}

        {photoFile && (
          <div className="field">
            {photoPreview && <img src={photoPreview} alt="Attached vehicle" style={{ maxWidth: '100%', borderRadius: 'var(--radius-md)', border: '1px solid var(--line)' }} />}
            <div className="row" style={{ marginTop: 'var(--space-3)' }}>
              <button type="button" className="btn" disabled={analyzing} onClick={analyzePhoto}>
                {analyzing ? 'Analyzing…' : 'Analyze with AI'}
              </button>
            </div>
            <label className="check-row" style={{ marginTop: 'var(--space-3)', textTransform: 'none' }}>
              <input type="checkbox" checked={addWatermark} onChange={(e) => setAddWatermark(e.target.checked)} />
              Stamp the photo with the entry date/time
            </label>
            {photoSource === 'upload' && (
              <label className="check-row" style={{ textTransform: 'none' }}>
                <input type="checkbox" checked={useExifDate} onChange={(e) => setUseExifDate(e.target.checked)} />
                Backdate entry using the photo's metadata date, if available
              </label>
            )}
          </div>
        )}

        {message && <div className={`alert ${message.kind === 'error' ? 'error' : message.kind === 'info' ? 'warning' : 'success'}`}>{message.text}</div>}

        {violation && violation.needs_warning && (
          <div className="alert error">
            <strong>Warning required</strong> &mdash; parked {violation.unique_days_parked} days in the last 30 (limit: 9) and has never been warned. Check &ldquo;Issue Warning&rdquo; below before submitting.
          </div>
        )}
        {violation && violation.can_tow && (
          <div className="alert error">
            <strong>Eligible for towing</strong> &mdash; parked {violation.unique_days_parked} days in the last 30 and was previously warned.
          </div>
        )}

        {pendingDuplicate ? (
          <div className="alert warning">
            <div>
              <strong className="plate">{licensePlate}</strong> was already logged today at {pendingDuplicate.time}. Add another entry anyway?
              <div className="row" style={{ marginTop: 'var(--space-3)' }}>
                <button className="btn" onClick={() => submit(true)} disabled={submitting}>Add Anyway</button>
                <button className="btn secondary" onClick={() => setPendingDuplicate(null)}>Skip</button>
              </div>
            </div>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void submit(false)
            }}
          >
            <div className="row">
              <div className="field">
                <label htmlFor="plate-input">License plate *</label>
                <input id="plate-input" type="text" value={licensePlate} onChange={(e) => setLicensePlate(e.target.value)} required />
              </div>
              <div className="field">
                <label htmlFor="tag-input">Tag number *</label>
                <input id="tag-input" type="text" value={tagNumber} onChange={(e) => setTagNumber(e.target.value)} required />
              </div>
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="make-input">Make</label>
                <input id="make-input" type="text" value={make} onChange={(e) => setMake(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="model-input">Model</label>
                <input id="model-input" type="text" value={model} onChange={(e) => setModel(e.target.value)} />
              </div>
            </div>
            <div className="row" style={{ marginBottom: 'var(--space-4)' }}>
              <label className="check-row"><input type="checkbox" checked={warned} onChange={(e) => setWarned(e.target.checked)} /> Issue Warning</label>
              <label className="check-row"><input type="checkbox" checked={towed} onChange={(e) => setTowed(e.target.checked)} /> Mark as Towed</label>
            </div>
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? 'Saving…' : 'Submit Entry'}
            </button>
          </form>
        )}
      </CollapsibleSection>

      {pendingDelete && (
        <ConfirmDeleteModal
          title={`Delete entry for ${pendingDelete.license_plate}?`}
          busy={deleting}
          onConfirm={confirmDeleteTodayEntry}
          onCancel={() => setPendingDelete(null)}
          fields={[
            { label: 'Plate', value: pendingDelete.license_plate },
            { label: 'Tag', value: pendingDelete.tag_number },
            { label: 'Make / Model', value: `${pendingDelete.make} ${pendingDelete.model}`.trim() || 'N/A' },
            { label: 'Time', value: pendingDelete.time },
            { label: 'Days (30d)', value: pendingDelete.days_30 },
            { label: 'Status', value: todayStatus(pendingDelete).label },
            { label: 'Photo', value: pendingDelete.photo_url ? <a href={pendingDelete.photo_url} target="_blank" rel="noreferrer">View photo</a> : 'None' },
          ]}
        />
      )}
    </div>
  )
}
