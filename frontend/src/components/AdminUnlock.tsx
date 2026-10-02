import { useState, type FormEvent } from 'react'
import { api } from '../api'
import StatusIconButton from './StatusIconButton'

export interface AdminStatus {
  configured: boolean
  authenticated: boolean
}

interface Props {
  status: AdminStatus | null
  onChange: () => void
}

/** Corner icon shown once unlocked — click to lock again. Replaces the
 * full-width green banner that used to stay on screen permanently. */
export function AdminUnlockIcon({ status, onChange }: Props) {
  if (!status?.authenticated) return null

  async function lock() {
    await api.adminLogout()
    onChange()
  }

  return (
    <StatusIconButton icon="🔓" label="Unlocked — click to lock" tone="ok">
      <p className="status-icon-popover-text">Unlocked — adding, deleting, and refreshing data is enabled on this device.</p>
      <button className="btn secondary" onClick={lock}>Lock</button>
    </StatusIconButton>
  )
}

/** Full-width passcode prompt — only shown while locked, since it's the one
 * state that actually needs the user's attention. */
export function AdminUnlockPrompt({ status, onChange }: Props) {
  const [passcode, setPasscode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!status?.configured || status.authenticated) return null

  async function unlock(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.adminLogin(passcode)
      setPasscode('')
      onChange()
    } catch {
      setError('Incorrect passcode.')
    } finally {
      setBusy(false)
    }
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
