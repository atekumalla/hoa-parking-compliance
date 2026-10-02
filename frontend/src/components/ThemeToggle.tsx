import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark'

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Toggles the "Citation Booklet" palette between its day (paper) and
 * night-patrol (inverted) variants. Persisted so it survives reloads. */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      className="btn secondary theme-toggle"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-pressed={isDark}
      title={isDark ? 'Switch to day shift (light)' : 'Switch to night patrol (dark)'}
    >
      {isDark ? 'Night Patrol' : 'Day Shift'}
    </button>
  )
}
