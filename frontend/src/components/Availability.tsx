import type { AvailabilityStatus, EntityScope, ReleaseAvailability } from '../api/types'
import { useSession } from '../state/session'

const labels: Record<AvailabilityStatus, string> = {
  DATABASE_NOT_CONNECTED: 'Database not connected',
  DATA_NOT_INGESTED: 'Dataset not loaded',
  RELEASE_VALIDATION_FAILED: 'Release validation failed',
  REFERENCE_UNAVAILABLE: 'Reference validation failed',
  RESEARCH_RELEASE_AVAILABLE: 'Local Research Available',
  RESEARCH_ACCESS_DISABLED: 'Research Access Disabled',
  PRODUCTION_NOT_APPROVED: 'Production Data Unavailable',
  PRODUCTION_RELEASE_AVAILABLE: 'Production Data Available',
  LOCAL_CATALOGUE_AVAILABLE: 'Local Catalogue Available',
}

export function useRelease(scope: EntityScope, version = 'FC27') {
  const { availability, availabilityLoading, researchOptIn } = useSession()
  const data = availability?.versions?.[version]?.[scope]
  const canOptIn = data?.research?.status === 'RESEARCH_RELEASE_AVAILABLE'
  const publicRelease = data?.local?.record_count ? data.local : data?.production
  const active = canOptIn && researchOptIn
  const status = availability?.database_status === 'DATABASE_NOT_CONNECTED'
    ? labels.DATABASE_NOT_CONNECTED : publicRelease?.record_count && !active && !canOptIn
    ? labels[publicRelease.status] : active
    ? 'Local Research Active' : data?.research
    ? labels[data.research.status] : data?.local?.status === 'DATA_NOT_INGESTED' && availability?.environment === 'local'
    ? labels.DATA_NOT_INGESTED : publicRelease
    ? labels[publicRelease.status] : availabilityLoading ? 'Checking availability' : 'Availability check unavailable'
  return { data, canOptIn, active, status, canBrowse: active || !!publicRelease?.record_count,
    canRecommend: active || !!publicRelease?.reference_ready }
}

export function ResearchControl({ scope, label, showStatus = true }: {
  scope: EntityScope; label: string; showStatus?: boolean
}) {
  const { setResearchOptIn, setGameVersion, refreshAvailability, availabilityLoading } = useSession()
  const { canOptIn, active, status } = useRelease(scope)
  return <div className="research-control">
    {showStatus && <span className="badge info" role="status">{status}</span>}
    {canOptIn ? <label className="checkbox"><input type="checkbox" checked={active} onChange={e => {
      if (e.target.checked) setGameVersion('FC27')
      setResearchOptIn(e.target.checked)
    }} /> {label}</label> : !availabilityLoading && <button className="btn ghost sm" type="button"
      onClick={refreshAvailability}>Check availability again</button>}
  </div>
}

export function ReleaseSummary({ release }: { release: ReleaseAvailability | null | undefined }) {
  if (!release) return null
  return <span>{labels[release.status]}{release.record_count != null && release.record_count > 0
    ? ' · ' + release.record_count.toLocaleString() + ' records' : ''}</span>
}
