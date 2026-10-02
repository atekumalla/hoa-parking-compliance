import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

interface Props {
  vehicle: { license_plate: string; tag_number: string; make: string; model: string }
  onClose: () => void
  onSuccess: () => void
}

/** Simplified add-entry form reused from the Scoreboard's "Quick Add" action —
 * same POST /api/entries endpoint as the main Add Vehicle page. */
export default function QuickAddModal({ vehicle, onClose, onSuccess }: Props) {
  const [warned, setWarned] = useState(false)
  const [towed, setTowed] = useState(false)
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [useExifDate, setUseExifDate] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingDuplicate, setPendingDuplicate] = useState<{ time: string } | null>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function submit(force = false) {
    setSubmitting(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('license_plate', vehicle.license_plate)
      form.append('tag_number', vehicle.tag_number)
      form.append('make', vehicle.make)
      form.append('model', vehicle.model)
      form.append('warned', String(warned))
      form.append('towed', String(towed))
      form.append('use_exif_date', String(useExifDate))
      form.append('add_watermark', 'false')
      form.append('force', String(force))
      if (photoFile) form.append('photo', photoFile)
      const result = await api.createEntry(form)
      if (result.photo_upload_warning) {
        setError(result.photo_upload_warning)
        return
      }
      onSuccess()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = e.detail as { duplicate_time?: string }
        setPendingDuplicate({ time: detail.duplicate_time ?? 'earlier today' })
      } else {
        setError((e as Error).message)
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="card modal" role="dialog" aria-modal="true" aria-labelledby="quick-add-title">
        <span className="eyebrow">Quick Add</span>
        <h3 id="quick-add-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span className="plate">{vehicle.license_plate}</span>
        </h3>
        <p>Tag {vehicle.tag_number} &middot; {vehicle.make} {vehicle.model}</p>

        <div className="row" style={{ marginBottom: 'var(--space-4)' }}>
          <label className="check-row"><input type="checkbox" checked={warned} onChange={(e) => setWarned(e.target.checked)} /> ⚠️ Issue Warning</label>
          <label className="check-row"><input type="checkbox" checked={towed} onChange={(e) => setTowed(e.target.checked)} /> 🚛 Mark as Towed</label>
        </div>

        <div className="field">
          <label htmlFor="quick-add-photo">Upload photo (optional)</label>
          <input id="quick-add-photo" type="file" accept="image/*,.heic" onChange={(e) => setPhotoFile(e.target.files?.[0] ?? null)} />
        </div>
        {photoFile && (
          <label className="check-row" style={{ textTransform: 'none' }}>
            <input type="checkbox" checked={useExifDate} onChange={(e) => setUseExifDate(e.target.checked)} /> Use photo's metadata date if available
          </label>
        )}

        {error && <div className="alert error">{error}</div>}

        {pendingDuplicate ? (
          <div className="alert warning">
            <span>
              <strong className="plate">{vehicle.license_plate}</strong> was already logged today at {pendingDuplicate.time}. Add another entry anyway?
            </span>
            <div className="row">
              <button className="btn secondary" onClick={() => setPendingDuplicate(null)}>Skip</button>
              <button className="btn" disabled={submitting} onClick={() => { setPendingDuplicate(null); void submit(true) }}>
                {submitting ? 'Saving…' : 'Add anyway'}
              </button>
            </div>
          </div>
        ) : (
          <div className="row" style={{ marginTop: 'var(--space-4)' }}>
            <button className="btn" disabled={submitting} onClick={() => submit(false)}>{submitting ? 'Saving…' : 'Submit'}</button>
            <button className="btn secondary" onClick={onClose}>❌ Cancel</button>
          </div>
        )}
      </div>
    </div>
  )
}
