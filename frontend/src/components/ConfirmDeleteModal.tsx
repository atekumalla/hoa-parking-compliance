import { useEffect, type ReactNode } from 'react'

export interface DetailField {
  label: string
  value: ReactNode
}

interface Props {
  title: string
  fields: DetailField[]
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Destructive-action confirmation showing the full entry being removed,
 * so a delete can never happen from a single accidental tap. */
export default function ConfirmDeleteModal({ title, fields, busy, onConfirm, onCancel }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="card modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-delete-title">
        <span className="eyebrow">Confirm Deletion</span>
        <h3 id="confirm-delete-title">{title}</h3>

        <dl className="detail-list">
          {fields.map((f) => (
            <div className="detail-row" key={f.label}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>

        <div className="alert warning">This permanently removes the entry and cannot be undone.</div>

        <div className="row" style={{ marginTop: 'var(--space-2)' }}>
          <button className="btn danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Deleting…' : 'Yes, Delete Entry'}
          </button>
          <button className="btn secondary" onClick={onCancel} disabled={busy}>No, Keep It</button>
        </div>
      </div>
    </div>
  )
}
