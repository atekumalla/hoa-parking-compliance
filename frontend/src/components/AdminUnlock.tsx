import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'

/** Shared-passcode unlock gate for destructive actions (add/delete entries,
 * delete photos, force refresh). Reads never require this. */
export default function AdminUnlock() {
  const [status, setStatus] = useState<{ configured: boolean; authenticated: boolean } | null>(null)
  const [passcode, setPasscode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    refresh()
  }, [])

  function refresh() {
    api.adminStatus().then(setStatus).catch(() => {})
  }

  async function unlock(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.adminLogin(passcode)
      setPasscode('')
      refresh()
    } catch {
      setError('Incorrect passcode.')
    } finally {
      setBusy(false)
    }
  }

  async function lock() {
    await api.adminLogout()
    refresh()
  }

  if (!status?.configured) return null

  if (status.authenticated) {
    return (
      <div className="alert success">
        <span>Unlocked — adding, deleting, and refreshing data is enabled on this device.</span>
        <button className="btn secondary" onClick={lock}>Lock</button>
      </div>
    )
  }

  return (
    <div className="alert warning">
      <form onSubmit={unlock} style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
        <span>Enter the passcode to add, delete, or refresh data.</span>
        <input
          type="password"
          value={passcode}
          onChange={(e) => setPasscode(e.target.value)}
          placeholder="Passcode"
          style={{ width: 160 }}
          aria-label="Admin passcode"
        />
        <button className="btn" type="submit" disabled={busy || !passcode}>{busy ? 'Checking…' : 'Unlock'}</button>
      </form>
      {error && <div style={{ marginTop: 'var(--space-2)', color: 'var(--danger-ink)' }}>{error}</div>}
    </div>
  )
}
