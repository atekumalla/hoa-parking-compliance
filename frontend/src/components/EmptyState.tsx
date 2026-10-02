import type { ReactNode } from 'react'

interface Props {
  title: string
  children?: ReactNode
}

/** A helpful empty state that teaches the interface instead of leaving blank space. */
export default function EmptyState({ title, children }: Props) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {children}
    </div>
  )
}
