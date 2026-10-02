interface Props {
  rows?: number
  width?: string
}

/** Shimmering placeholder bars shown while a section's first fetch is in flight. */
export default function Skeleton({ rows = 3, width = '100%' }: Props) {
  return (
    <div aria-hidden="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ width: i === rows - 1 ? '60%' : width, marginBottom: 10 }}
        />
      ))}
    </div>
  )
}
