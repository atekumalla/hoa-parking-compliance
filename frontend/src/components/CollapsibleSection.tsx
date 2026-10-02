import { useState, type ReactNode } from 'react'

interface Props {
  /** Heading content (an <h2>/<h3>, optionally preceded by an eyebrow) rendered left of the toggle. */
  title: ReactNode
  /** Extra controls (e.g. a Refresh button) rendered before the Collapse/Expand toggle. */
  actions?: ReactNode
  defaultCollapsed?: boolean
  children: ReactNode
}

/** A card section with a Collapse/Expand toggle top-right of its header.
 * Animates via grid-template-rows so height is never animated directly. */
export default function CollapsibleSection({ title, actions, defaultCollapsed = false, children }: Props) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
        <div>{title}</div>
        <div className="row" style={{ width: 'auto' }}>
          {actions}
          <button
            type="button"
            className="btn secondary"
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        </div>
      </div>
      <div className={`collapsible ${collapsed ? 'collapsed' : ''}`}>
        <div>{children}</div>
      </div>
    </div>
  )
}
