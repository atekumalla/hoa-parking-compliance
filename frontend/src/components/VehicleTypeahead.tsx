import { useEffect, useMemo, useRef, useState } from 'react'
import { KnownVehicle } from '../api'

interface Props {
  id: string
  vehicles: KnownVehicle[]
  placeholder?: string
  onSelect: (vehicle: KnownVehicle) => void
}

/** Text input that narrows a dropdown of known vehicles as the user types,
 * mirroring the old Streamlit app's filtered selectbox behavior. */
export default function VehicleTypeahead({ id, vehicles, placeholder, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return vehicles
    return vehicles.filter((v) => v.label.toLowerCase().includes(q))
  }, [query, vehicles])

  useEffect(() => {
    setHighlighted(0)
  }, [query, open])

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  function choose(vehicle: KnownVehicle) {
    onSelect(vehicle)
    setQuery('')
    setOpen(false)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true)
      return
    }
    if (!open) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((i) => Math.min(i + 1, matches.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      if (matches[highlighted]) {
        e.preventDefault()
        choose(matches[highlighted])
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="typeahead" ref={rootRef}>
      <input
        type="text"
        id={id}
        role="combobox"
        aria-expanded={open && matches.length > 0}
        aria-controls={`${id}-listbox`}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {open && matches.length > 0 && (
        <ul className="typeahead-list" id={`${id}-listbox`} role="listbox">
          {matches.map((v, i) => (
            <li
              key={v.label}
              role="option"
              aria-selected={i === highlighted}
              className={i === highlighted ? 'active' : ''}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(v)
              }}
              onMouseEnter={() => setHighlighted(i)}
            >
              {v.label}
            </li>
          ))}
        </ul>
      )}
      {open && query.trim() && matches.length === 0 && (
        <ul className="typeahead-list" role="listbox">
          <li className="empty">No matching vehicles</li>
        </ul>
      )}
    </div>
  )
}
