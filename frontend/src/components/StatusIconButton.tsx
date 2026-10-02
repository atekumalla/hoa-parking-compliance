import { useEffect, useRef, useState, type ReactNode } from 'react'

interface Props {
  icon: ReactNode
  label: string
  tone: 'ok' | 'warn'
  children: ReactNode
}

/** Compact corner badge that expands into a popover on click — used so a
 * persistent "you're unlocked / signed in" state doesn't eat a full-width
 * banner forever once it's no longer actionable. */
export default function StatusIconButton({ icon, label, tone, children }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  return (
    <div className="status-icon" ref={rootRef}>
      <button
        type="button"
        className={`status-icon-btn ${tone}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={label}
        title={label}
      >
        {icon}
      </button>
      {open && (
        <div className="status-icon-popover" role="menu" onClick={() => setOpen(false)}>
          {children}
        </div>
      )}
    </div>
  )
}
