import { api } from '../api'
import StatusIconButton from './StatusIconButton'

export interface GoogleAuthStatus {
  configured: boolean
  authenticated: boolean
}

interface Props {
  status: GoogleAuthStatus | null
  onChange: () => void
}

/** Corner icon shown once signed in to Google — click to sign out. Replaces
 * the full-width green banner that used to stay on screen permanently. */
export default function GoogleAuthIcon({ status, onChange }: Props) {
  if (!status?.authenticated) return null

  function logout() {
    api.logout().then(onChange)
  }

  return (
    <StatusIconButton icon={<span className="google-g-icon" aria-hidden="true">G</span>} label="Signed in to Google — click to sign out" tone="ok">
      <p className="status-icon-popover-text">Signed in to Google — photo uploads enabled.</p>
      <button className="btn secondary" onClick={logout}>Sign out</button>
    </StatusIconButton>
  )
}
