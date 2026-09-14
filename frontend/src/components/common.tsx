import type { ReactNode } from 'react'
import { useEffect } from 'react'
import type { ApiError } from '../api/client'
import type { FitValue } from '../api/types'
import { FACADE_LABELS, UNKNOWN_LABEL, isUnknown, num, ovrClass, pct } from '../lib/format'

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  )
}

export function Empty({ title, hint, children }: {
  title: string; hint?: string; children?: ReactNode
}) {
  return (
    <div className="empty">
      <div className="big" aria-hidden="true">◇</div>
      <div style={{ fontWeight: 650, color: 'var(--text-dim)' }}>{title}</div>
      {hint && <div className="small mt1" style={{ maxWidth: '52ch', marginInline: 'auto' }}>{hint}</div>}
      {children && <div className="mt2 row" style={{ justifyContent: 'center' }}>{children}</div>}
    </div>
  )
}

/** Safe error surface: shows the backend's detail and request_id, never a stack. */
export function ErrorBox({ error, onRetry }: { error: ApiError | null; onRetry?: () => void }) {
  if (!error) return null
  const title = error.status === 404 ? 'Not available'
    : error.status === 401 ? 'Authentication required'
    : error.status === 403 ? 'Not permitted'
    : error.status === 422 ? 'Request rejected'
    : error.status === 429 ? 'Too many requests'
    : 'Something went wrong'
  return (
    <div className="error-box" role="alert">
      <div className="t">{title} <span className="faint mono">({error.status})</span></div>
      <div className="small">{error.detail}</div>
      {error.requestId && <div className="rid">request_id: {error.requestId}</div>}
      {error.status === 429 && <div className="rid">Wait a moment, then try again.</div>}
      {onRetry && <button type="button" className="btn sm mt1" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Ovr({ value }: { value: number | null | undefined }) {
  if (isUnknown(value)) return <span className="ovr unknown-val" title={UNKNOWN_LABEL}>–</span>
  return <span className={`ovr ${ovrClass(value)}`}>{value}</span>
}

export function Pos({ value }: { value: string | null | undefined }) {
  if (isUnknown(value)) return <span className="pos unknown-val" title={UNKNOWN_LABEL}>?</span>
  return <span className="pos">{value}</span>
}

export function Unknown({ title = 'Not present in ingested data' }: { title?: string }) {
  return <span className="unknown-val" title={title}>{UNKNOWN_LABEL}</span>
}

/** A value that must never be silently rendered as 0 when missing. */
export function Value({ v, digits = 0 }: { v: number | null | undefined; digits?: number }) {
  return isUnknown(v) ? <Unknown /> : <>{num(v, digits)}</>
}

export function Bar({ value, max = 99, kind }: {
  value: number | null | undefined; max?: number; kind?: 'info' | 'warn' | 'na'
}) {
  const unknown = isUnknown(value)
  const w = unknown ? 100 : Math.max(0, Math.min(100, ((value as number) / max) * 100))
  const cls = unknown ? 'na' : kind
  return (
    <div className={`bar ${cls || ''}`} role="img"
         aria-label={unknown ? `${UNKNOWN_LABEL}` : `${value} of ${max}`}>
      <span style={{ width: `${w}%` }} />
    </div>
  )
}

export function Facades({ f }: { f: Record<string, number | null> }) {
  return (
    <div className="row" style={{ gap: '.4rem' }}>
      {Object.entries(FACADE_LABELS).map(([key, lbl]) => (
        <span key={key} className="tiny nowrap" title={`${key}: ${isUnknown(f[key]) ? UNKNOWN_LABEL : f[key]}`}>
          <span className="faint">{lbl}</span>{' '}
          <span className="mono" style={{ fontWeight: 650 }}>
            {isUnknown(f[key]) ? '–' : f[key]}
          </span>
        </span>
      ))}
    </div>
  )
}

export function AttrRows({ attrs, codes }: {
  attrs: Record<string, number | null | undefined>; codes: string[]
}) {
  return (
    <div className="attr-grid">
      {codes.map((c) => (
        <div className="attr" key={c}>
          <span className="lbl" title={c}>{c}</span>
          <span className="val">{isUnknown(attrs[c]) ? <Unknown /> : attrs[c]}</span>
          <Bar value={attrs[c] as number | null} />
        </div>
      ))}
    </div>
  )
}

const FIT_CLASS: Record<string, string> = {
  KNOWN: 'ok', UNKNOWN: 'unknown', INSUFFICIENT_EVIDENCE: 'warn',
}

export function FitBadge({ fit }: { fit: FitValue | null | undefined }) {
  if (!fit) return <span className="badge unknown">{UNKNOWN_LABEL}</span>
  return (
    <span className={`badge ${FIT_CLASS[fit.status] || 'unknown'}`} title={fit.reason || ''}>
      {fit.status === 'KNOWN' ? num(fit.value, 2) : fit.status.replace(/_/g, ' ')}
    </span>
  )
}

export function ScoreBar({ score, label }: { score: number | null; label?: string }) {
  return (
    <div style={{ minWidth: 130 }}>
      <div className="row" style={{ gap: '.4rem', marginBottom: '.2rem' }}>
        <span className="mono" style={{ fontWeight: 700, color: 'var(--accent)' }}>
          {isUnknown(score) ? UNKNOWN_LABEL : (score as number).toFixed(3)}
        </span>
        {label && <span className="tiny faint">{label}</span>}
      </div>
      <Bar value={isUnknown(score) ? null : (score as number) * 100} max={100} />
    </div>
  )
}

export function ConfidenceBadge({ score }: { score: number | null | undefined }) {
  if (isUnknown(score)) return <span className="badge unknown">confidence {UNKNOWN_LABEL}</span>
  const s = score as number
  const cls = s >= 0.8 ? 'ok' : s >= 0.55 ? 'info' : 'warn'
  const lbl = s >= 0.8 ? 'high' : s >= 0.55 ? 'medium' : 'low'
  return <span className={`badge ${cls}`}>confidence {lbl} · {pct(s)}%</span>
}

export function Modal({ title, onClose, children, wide }: {
  title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" style={wide ? { maxWidth: 980 } : undefined}
           onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3 className="mb0">{title}</h3>
          <button type="button" className="x" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, children, hint }: {
  label: string; children: ReactNode; hint?: string
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint && <span className="tiny faint">{hint}</span>}
    </div>
  )
}

/** Radar of the six facade stats. Missing facets are drawn as gaps, not zeros. */
export function FacadeRadar({ values, size = 168 }: {
  values: Record<string, number | null>; size?: number
}) {
  const keys = Object.keys(FACADE_LABELS)
  const cx = size / 2, cy = size / 2, r = size / 2 - 26
  const pt = (i: number, frac: number) => {
    const a = (Math.PI * 2 * i) / keys.length - Math.PI / 2
    return [cx + Math.cos(a) * r * frac, cy + Math.sin(a) * r * frac] as const
  }
  const ring = (frac: number) =>
    keys.map((_, i) => pt(i, frac).join(',')).join(' ')
  const known = keys.map((k, i) => ({ k, i, v: values[k] }))
  const poly = known
    .filter((d) => !isUnknown(d.v))
    .map((d) => pt(d.i, Math.max(0.02, (d.v as number) / 99)).join(','))
    .join(' ')
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
         aria-label="Facet radar; missing facets are omitted, never drawn as zero">
      {[0.33, 0.66, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke="var(--line-strong)" strokeWidth={1} />
      ))}
      {keys.map((_, i) => {
        const [x, y] = pt(i, 1)
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--line)" strokeWidth={1} />
      })}
      {poly && <polygon points={poly} fill="rgba(0,224,138,.22)" stroke="var(--accent)" strokeWidth={1.6} />}
      {keys.map((k, i) => {
        const [x, y] = pt(i, 1.2)
        const v = values[k]
        return (
          <text key={k} x={x} y={y} textAnchor="middle" dominantBaseline="middle"
                fontSize={10.5} fontWeight={700} letterSpacing=".04em"
                fill={isUnknown(v) ? 'var(--unknown)' : 'var(--text-dim)'}>
            {FACADE_LABELS[k]} {isUnknown(v) ? '–' : v}
          </text>
        )
      })}
    </svg>
  )
}

export function Stars({ n, max = 5 }: { n: number | null | undefined; max?: number }) {
  if (isUnknown(n)) return <Unknown />
  return <span className="nowrap" aria-label={`${n} of ${max}`}>{'★'.repeat(n as number)}
    <span className="faint">{'★'.repeat(Math.max(0, max - (n as number)))}</span></span>
}
