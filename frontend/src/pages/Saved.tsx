import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useApi } from '../lib/useApi'
import { useSession } from '../state/session'
import { Empty, ErrorBox, Loading, Ovr, Pos } from '../components/common'
import { UNKNOWN_LABEL, dateShort } from '../lib/format'

interface SavedItem {
  id: string
  entity_type: string
  entity_id: string
  note: string | null
  created_at: string
  game_version: string
  display_name?: string | null
  position_primary?: string | null
  overall_rating?: number | null
  nation?: string | null
}

export default function Saved() {
  const { gameVersion, notify } = useSession()
  const saved = useApi<{ items: SavedItem[]; total: number }>('/api/saved-players')

  async function unsave(item: SavedItem) {
    try {
      await api.del(`/api/saved-players/${item.entity_id}?entity_type=${item.entity_type}`)
      saved.reload()
      notify('ok', 'Removed from saved.')
    } catch (e: any) {
      notify('bad', e.detail || 'Could not remove.', e.requestId)
    }
  }

  const items = (saved.data?.items ?? [])
  const shown = items.filter((i) => i.game_version === gameVersion)
  const other = items.filter((i) => i.game_version !== gameVersion)

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mb0">Saved players</h1>
          <div className="sub small">
            {saved.data ? `${saved.data.total} saved across all versions · showing ${shown.length} for ${gameVersion}` : 'Your shortlist.'}
          </div>
        </div>
      </div>

      <ErrorBox error={saved.error} onRetry={saved.reload} />
      {saved.loading && <div className="card"><Loading /></div>}

      {!saved.loading && items.length === 0 && (
        <div className="card">
          <Empty title="Nothing saved yet"
                 hint="Use the ☆ button in search results or on a player page to build a shortlist.">
            <Link className="btn primary sm" to="/search">Browse players</Link>
          </Empty>
        </div>
      )}

      {shown.length > 0 && (
        <div className="card mb2" style={{ padding: 0, overflowX: 'auto' }}>
          <table className="data">
            <thead>
              <tr><th>OVR</th><th>Pos</th><th>Player</th><th>Nation</th>
                  <th>Saved</th><th>Note</th><th /></tr>
            </thead>
            <tbody>
              {shown.map((i) => (
                <tr key={i.id}>
                  <td><Ovr value={i.overall_rating ?? null} /></td>
                  <td><Pos value={i.position_primary ?? null} /></td>
                  <td>
                    <Link to={`/players/${i.entity_id}`} style={{ fontWeight: 600 }}>
                      {i.display_name ?? <span className="unknown-val">entity {i.entity_id.slice(0, 8)}…</span>}
                    </Link>
                  </td>
                  <td className="small">{i.nation ?? <span className="unknown-val">{UNKNOWN_LABEL}</span>}</td>
                  <td className="small faint">{dateShort(i.created_at)}</td>
                  <td className="small muted">{i.note ?? '—'}</td>
                  <td className="right">
                    <button className="btn ghost sm danger" onClick={() => unsave(i)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {other.length > 0 && (
        <div className="callout info small">
          <div className="t">{other.length} saved item(s) in other game versions</div>
          Saved entries never cross versions. Switch the version above to see them:
          <div className="row mt1">
            {other.map((i) => (
              <span key={i.id} className="badge">
                {i.game_version}: {i.display_name ?? i.entity_id.slice(0, 8)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
