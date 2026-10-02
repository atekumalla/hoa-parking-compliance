import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { api } from './api'
import AddVehiclePage from './pages/AddVehiclePage'
import ScoreboardPage from './pages/ScoreboardPage'
import VehicleHistoryPage from './pages/VehicleHistoryPage'
import StoragePage from './pages/StoragePage'
import RulesPage from './pages/RulesPage'
import ThemeToggle from './components/ThemeToggle'
import AdminUnlock from './components/AdminUnlock'

export default function App() {
  const [links, setLinks] = useState<{ sheet_url: string; drive_url: string } | null>(null)
  const [auth, setAuth] = useState<{ configured: boolean; authenticated: boolean } | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    api.links().then(setLinks).catch(() => {})
    refreshAuth()

    const params = new URLSearchParams(window.location.search)
    const error = params.get('auth_error')
    if (error) {
      setAuthError(
        error === 'state_mismatch'
          ? 'Google sign-in failed a security check (state mismatch). Please try signing in again.'
          : 'Google sign-in failed. Please try again.'
      )
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  function refreshAuth() {
    api.authStatus().then(setAuth).catch(() => {})
  }

  return (
    <div className="app-container">
      <header className="masthead">
        <div className="masthead-toggle"><ThemeToggle /></div>
        <span className="eyebrow">Station 121 &middot; Guest Parking Enforcement</span>
        <h1>Compliance Tracker</h1>
        {links && (
          <p className="masthead-meta">
            <a href={links.sheet_url} target="_blank" rel="noreferrer">📎 Open Google Sheet</a>
            <a href={links.drive_url} target="_blank" rel="noreferrer">📂 Open Drive Photos</a>
          </p>
        )}
      </header>

      <AdminUnlock />

      {authError && (
        <div className="alert error">
          <span>{authError}</span>
          <button className="btn secondary" onClick={() => setAuthError(null)}>Dismiss</button>
        </div>
      )}

      {auth?.configured && (
        <div className={`alert ${auth.authenticated ? 'success' : 'warning'}`}>
          {auth.authenticated ? (
            <>
              <span>Signed in to Google — photo uploads enabled.</span>
              <button className="btn secondary" onClick={() => api.logout().then(refreshAuth)}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <span>Sign in with Google to enable photo uploads to Drive.</span>
              <a className="btn" href="/api/auth/login">Sign in with Google</a>
            </>
          )}
        </div>
      )}

      <nav className="nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>Add Vehicle</NavLink>
        <NavLink to="/scoreboard" className={({ isActive }) => (isActive ? 'active' : '')}>Scoreboard</NavLink>
        <NavLink to="/history" className={({ isActive }) => (isActive ? 'active' : '')}>Vehicle History</NavLink>
        <NavLink to="/storage" className={({ isActive }) => (isActive ? 'active' : '')}>Storage</NavLink>
        <NavLink to="/rules" className={({ isActive }) => (isActive ? 'active' : '')}>Rules</NavLink>
      </nav>

      <Routes>
        <Route path="/" element={<AddVehiclePage />} />
        <Route path="/scoreboard" element={<ScoreboardPage />} />
        <Route path="/history" element={<VehicleHistoryPage />} />
        <Route path="/storage" element={<StoragePage />} />
        <Route path="/rules" element={<RulesPage />} />
      </Routes>
    </div>
  )
}
