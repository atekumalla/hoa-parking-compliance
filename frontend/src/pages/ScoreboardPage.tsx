import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ScoreboardData, ScoreboardVehicle } from '../api'
import QuickAddModal from '../components/QuickAddModal'
import CollapsibleSection from '../components/CollapsibleSection'
import EmptyState from '../components/EmptyState'
import Skeleton from '../components/Skeleton'

const PAGE_SIZE = 10

export default function ScoreboardPage() {
  const [data, setData] = useState<ScoreboardData | null>(null)
  const [page, setPage] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const [quickAddVehicle, setQuickAddVehicle] = useState<ScoreboardVehicle | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  function load() {
    return api.scoreboard().then((d) => { setData(d); setError(null) }).catch((e) => setError((e as Error).message))
  }

  async function refresh() {
    setRefreshing(true)
    try {
      await api.refreshData()
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRefreshing(false)
    }
  }

  if (!data) {
    return (
      <div className="card">
        <span className="eyebrow">Scoreboard</span>
        <h2>Loading records&hellip;</h2>
        {error ? <div className="alert error">{error}</div> : <Skeleton rows={4} />}
      </div>
    )
  }

  const vehicles = data.vehicles
  const totalPages = Math.max(1, Math.ceil(vehicles.length / PAGE_SIZE))
  const clampedPage = Math.min(page, totalPages - 1)
  const pageData = vehicles.slice(clampedPage * PAGE_SIZE, clampedPage * PAGE_SIZE + PAGE_SIZE)

  return (
    <div>
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <span className="eyebrow">Enforcement overview</span>
            <h2 style={{ marginBottom: 0 }}>Scoreboard</h2>
          </div>
          <button className="btn secondary" onClick={refresh} disabled={refreshing}>
            {refreshing ? 'Refreshing…' : 'Refresh Data'}
          </button>
        </div>
        {error && <div className="alert error" style={{ marginTop: 'var(--space-3)' }}>{error}</div>}
      </div>

      <CollapsibleSection title={<h3 style={{ marginBottom: 0 }}>Top 10 Tags &middot; Last 90 Days</h3>}>
        {data.top_tags_90d.length === 0 ? (
          <EmptyState title="No tag activity in the last 90 days." />
        ) : (
          <table>
            <thead><tr><th>Tag</th><th>Times Used</th><th>Unique Days</th><th>Last Seen</th><th>Plates</th></tr></thead>
            <tbody>
              {data.top_tags_90d.map((t) => (
                <tr key={t.tag_number}>
                  <td>
                    <Link className="plate" to="/history" state={{ prefillTag: t.tag_number }} title={`View history for tag ${t.tag_number}`}>
                      {t.tag_number}
                    </Link>
                  </td>
                  <td>{t.times_used}</td>
                  <td>{t.unique_days}</td>
                  <td>{t.last_seen}</td>
                  <td>
                    {t.plates.split(', ').map((plate, i) => (
                      <span key={plate}>
                        {i > 0 && ', '}
                        <Link to="/history" state={{ prefillPlate: plate }} title={`View history for plate ${plate}`}>{plate}</Link>
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CollapsibleSection>

      <CollapsibleSection title={<h3 style={{ marginBottom: 0 }}>Needing Attention</h3>}>
        <p>Vehicles never warned, ranked by unique days parked in the last 30.</p>
        {data.unwarned.length === 0 ? (
          <EmptyState title="Every vehicle in the 30-day window has already been warned." />
        ) : (
          <table>
            <thead><tr><th>Plate</th><th>Tag</th><th>Days (30d)</th><th>Last Seen</th></tr></thead>
            <tbody>
              {data.unwarned.map((v) => (
                <tr key={v.license_plate} className={v.over_limit ? 'severity-danger' : v.days_30 >= 7 ? 'severity-warn' : undefined}>
                  <td>
                    <Link className="plate" to="/history" state={{ prefillPlate: v.license_plate }} title={`View history for plate ${v.license_plate}`}>
                      {v.license_plate}
                    </Link>
                  </td>
                  <td>
                    {v.tag_number && (
                      <Link to="/history" state={{ prefillTag: v.tag_number }} title={`View history for tag ${v.tag_number}`}>{v.tag_number}</Link>
                    )}
                  </td>
                  <td>{v.days_30}</td>
                  <td>{v.last_seen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CollapsibleSection>

      <CollapsibleSection title={<h3 style={{ marginBottom: 0 }}>Most Frequent Vehicles &middot; Last 30 Days</h3>}>
        <p>
          Showing {clampedPage * PAGE_SIZE + 1}–{Math.min((clampedPage + 1) * PAGE_SIZE, vehicles.length)} of {vehicles.length}
        </p>

        {pageData.length === 0 ? (
          <EmptyState title="No vehicles parked in the last 30 days." />
        ) : (
          pageData.map((v) => {
            const statusClass = v.towed ? 'status-danger' : v.warned ? 'status-warn' : ''
            const stampClass = v.towed ? 'danger' : v.warned ? 'warn' : 'ok'
            const stampText = v.towed ? 'Towed' : v.warned ? 'Warned' : 'Compliant'
            return (
              <div key={v.license_plate} className={`vehicle-card ${statusClass}`}>
                <h4>
                  <Link className="plate" to="/history" state={{ prefillPlate: v.license_plate }} title={`View history for plate ${v.license_plate}`}>
                    {v.license_plate}
                  </Link>
                  <span className={`stamp ${stampClass}`}>{stampText}</span>
                </h4>
                <p style={{ margin: '0 0 4px' }}>
                  {v.make} {v.model} &middot; Tag{' '}
                  {v.tag_number ? (
                    <Link to="/history" state={{ prefillTag: v.tag_number }} title={`View history for tag ${v.tag_number}`}>{v.tag_number}</Link>
                  ) : 'N/A'}
                </p>
                <p style={{ margin: 0 }}>
                  <strong>{v.unique_days_parked}</strong> unique days parked &middot; last seen {v.last_seen ? new Date(v.last_seen).toLocaleDateString() : 'N/A'}
                </p>
                <div className="row" style={{ marginTop: 'var(--space-3)' }}>
                  <button className="btn secondary" onClick={() => setQuickAddVehicle(v)}>Quick Add</button>
                </div>
              </div>
            )
          })
        )}

        <div className="pagination">
          <button className="btn secondary" disabled={clampedPage === 0} onClick={() => setPage(clampedPage - 1)}>&larr; Previous</button>
          <span>Page {clampedPage + 1} of {totalPages}</span>
          <button className="btn secondary" disabled={clampedPage >= totalPages - 1} onClick={() => setPage(clampedPage + 1)}>Next &rarr;</button>
        </div>
      </CollapsibleSection>

      {quickAddVehicle && (
        <QuickAddModal
          vehicle={quickAddVehicle}
          onClose={() => setQuickAddVehicle(null)}
          onSuccess={() => {
            setQuickAddVehicle(null)
            void load()
          }}
        />
      )}
    </div>
  )
}
