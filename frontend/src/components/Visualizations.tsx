/**
 * EA FC Intelligence — Stadium 2.0 Visualizations Primitives
 * Reusable data visualization components adhering to football-first analytical hierarchy.
 */

import { UNKNOWN_LABEL, prettyAttr } from '../lib/format'

export interface SuitabilityScoreProps {
  score: number | null | undefined
  contextLabel?: string
  size?: 'sm' | 'md' | 'lg'
  subtitle?: string
}

export function SuitabilityScore({ score, contextLabel, size = 'md', subtitle }: SuitabilityScoreProps) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return (
      <div className={`suitability-score-gauge score-${size}`}>
        <span className="suitability-score-val unknown">{UNKNOWN_LABEL}</span>
        {contextLabel && <span className="suitability-score-label">{contextLabel}</span>}
      </div>
    )
  }

  // Clamped 0.0 - 1.0 or 0 - 100
  const normalized = score <= 1.0 ? score * 100 : score
  const displayScore = score <= 1.0 ? score.toFixed(3) : score.toFixed(1)
  const tier = normalized >= 85 ? 'elite' : normalized >= 72 ? 'high' : normalized >= 60 ? 'good' : 'fair'

  const strokeDashoffset = 100 - Math.min(100, Math.max(0, normalized))

  return (
    <div className={`suitability-score-gauge score-${size} tier-${tier}`} role="img" aria-label={`Suitability score: ${displayScore} for ${contextLabel ?? 'tactical context'}`}>
      <div className="gauge-radial-wrap">
        <svg viewBox="0 0 36 36" className="gauge-svg" aria-hidden="true">
          <path
            className="gauge-bg"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            className="gauge-meter"
            strokeDasharray="100, 100"
            strokeDashoffset={strokeDashoffset}
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <span className="gauge-value">{displayScore}</span>
      </div>
      {(contextLabel || subtitle) && (
        <div className="gauge-meta">
          {contextLabel && <span className="gauge-context">{contextLabel}</span>}
          {subtitle && <span className="gauge-sub">{subtitle}</span>}
        </div>
      )}
    </div>
  )
}

export interface AttributeBarProps {
  label: string
  value: number | null | undefined
  max?: number
  delta?: number
  showValue?: boolean
}

export function AttributeBar({ label, value, max = 99, delta, showValue = true }: AttributeBarProps) {
  const isKnown = value !== null && value !== undefined && !Number.isNaN(value)
  const pct = isKnown ? Math.min(100, Math.max(3, (value / max) * 100)) : 0
  const fillTier = isKnown ? (value >= 86 ? 'fill-elite' : value >= 75 ? 'fill-high' : '') : ''

  return (
    <div className="attr-bar-container">
      <div className="attr-bar-header">
        <span className="attr-bar-label">{prettyAttr(label)}</span>
        <div className="attr-bar-numbers">
          {delta !== undefined && delta !== 0 && (
            <span className={`delta-pill ${delta > 0 ? 'pos' : 'neg'}`} aria-label={`Delta: ${delta > 0 ? '+' : ''}${delta}`}>
              {delta > 0 ? `+${delta}` : delta}
            </span>
          )}
          {showValue && (
            <span className={`attr-bar-value ${isKnown ? '' : 'faint'}`}>
              {isKnown ? value : UNKNOWN_LABEL}
            </span>
          )}
        </div>
      </div>
      <div className="attr-bar-track">
        {isKnown ? (
          <div
            className={`attr-bar-fill ${fillTier}`}
            style={{ width: `${pct}%` }}
            role="progressbar"
            aria-valuenow={value}
            aria-valuemin={0}
            aria-valuemax={max}
            aria-label={`${label}: ${value}`}
          />
        ) : (
          <div
            className="attr-bar-fill unknown"
            style={{
              width: '100%',
              background: 'repeating-linear-gradient(45deg, #1c2636, #1c2636 4px, #131c28 4px, #131c28 8px)',
            }}
          />
        )}
      </div>
    </div>
  )
}

export interface TacticalDeltaMatrixProps {
  basePlayer: {
    name: string
    facades: Record<string, number | null | undefined>
    overall_rating?: number | null
  }
  comparePlayer: {
    name: string
    facades: Record<string, number | null | undefined>
    overall_rating?: number | null
  }
}

export function TacticalDeltaMatrix({ basePlayer, comparePlayer }: TacticalDeltaMatrixProps) {
  const facets = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physicality']

  return (
    <div className="tactical-delta-matrix card tight">
      <div className="matrix-head row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '0.6rem' }}>
        <div>
          <span className="tiny faint">BASE CANDIDATE</span>
          <div className="strong" style={{ color: 'var(--accent-cyan)' }}>{basePlayer.name}</div>
        </div>
        <span className="muted small">VS</span>
        <div style={{ textAlign: 'right' }}>
          <span className="tiny faint">COMPARED TO</span>
          <div className="strong" style={{ color: 'var(--accent-lime)' }}>{comparePlayer.name}</div>
        </div>
      </div>

      <div className="matrix-body col" style={{ gap: '0.55rem' }}>
        {facets.map((facet) => {
          const valA = basePlayer.facades[facet]
          const valB = comparePlayer.facades[facet]
          const delta = (valB !== null && valB !== undefined && valA !== null && valA !== undefined)
            ? valB - valA
            : undefined

          return (
            <div key={facet} className="matrix-row">
              <AttributeBar
                label={facet}
                value={valB}
                delta={delta}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

export interface EvidenceBadgeProps {
  status: string | null | undefined
  count?: number
  label?: string
}

export function EvidenceBadge({ status, count, label }: EvidenceBadgeProps) {
  const st = (status ?? 'UNKNOWN').toUpperCase()
  let badgeClass = 'badge unknown'
  let text = label || st.replace(/_/g, ' ')

  if (st === 'VERIFIED' || st === 'COMPLETE' || st === 'RESOLVED') {
    badgeClass = 'badge ok'
  } else if (st === 'PARTIAL' || st === 'REVIEW_REQUIRED' || st === 'PROVISIONAL') {
    badgeClass = 'badge warn'
  } else if (st === 'INSUFFICIENT' || st === 'DISPUTED' || st === 'REJECTED') {
    badgeClass = 'badge bad'
  }

  return (
    <span className={`evidence-badge ${badgeClass}`} title={`Evidence status: ${text}`}>
      {text}
      {count !== undefined && count > 0 && <span className="evidence-count">({count})</span>}
    </span>
  )
}

export interface TacticalRadarProps {
  title?: string
  facadesA: Record<string, number | null | undefined>
  nameA: string
  facadesB?: Record<string, number | null | undefined>
  nameB?: string
}

export function TacticalRadar({ title, facadesA, nameA, facadesB, nameB }: TacticalRadarProps) {
  const categories = [
    { key: 'pace', label: 'PAC' },
    { key: 'shooting', label: 'SHO' },
    { key: 'passing', label: 'PAS' },
    { key: 'dribbling', label: 'DRI' },
    { key: 'defending', label: 'DEF' },
    { key: 'physicality', label: 'PHY' },
  ]

  const size = 200
  const center = size / 2
  const radius = 70
  const angleStep = (Math.PI * 2) / categories.length

  const getPoints = (facades: Record<string, number | null | undefined>) => {
    return categories.map((cat, i) => {
      const val = facades[cat.key] ?? 50
      const r = (Math.min(99, Math.max(10, val)) / 99) * radius
      const angle = i * angleStep - Math.PI / 2
      const x = center + r * Math.cos(angle)
      const y = center + r * Math.sin(angle)
      return `${x},${y}`
    }).join(' ')
  }

  return (
    <div className="tactical-radar-card card tight">
      {title && <div className="section-title mb1">{title}</div>}
      <div className="radar-svg-wrap" style={{ display: 'flex', justifyContent: 'center', position: 'relative' }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label="Tactical facet radar">
          {/* Concentric grid rings */}
          {[0.25, 0.5, 0.75, 1.0].map((ring) => (
            <polygon
              key={ring}
              points={categories.map((_, i) => {
                const r = ring * radius
                const angle = i * angleStep - Math.PI / 2
                return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`
              }).join(' ')}
              fill="none"
              stroke="var(--border-subtle)"
              strokeWidth="1"
            />
          ))}

          {/* Spokes */}
          {categories.map((cat, i) => {
            const angle = i * angleStep - Math.PI / 2
            const x2 = center + radius * Math.cos(angle)
            const y2 = center + radius * Math.sin(angle)
            return (
              <line
                key={cat.key}
                x1={center}
                y1={center}
                x2={x2}
                y2={y2}
                stroke="var(--border-subtle)"
                strokeWidth="1"
              />
            )
          })}

          {/* Player A Polygon */}
          <polygon
            points={getPoints(facadesA)}
            fill="rgba(82, 201, 232, 0.25)"
            stroke="var(--accent-cyan)"
            strokeWidth="2"
          />

          {/* Player B Polygon (Optional) */}
          {facadesB && (
            <polygon
              points={getPoints(facadesB)}
              fill="rgba(184, 245, 122, 0.25)"
              stroke="var(--accent-lime)"
              strokeWidth="2"
            />
          )}

          {/* Labels */}
          {categories.map((cat, i) => {
            const angle = i * angleStep - Math.PI / 2
            const lx = center + (radius + 18) * Math.cos(angle)
            const ly = center + (radius + 18) * Math.sin(angle)
            return (
              <text
                key={cat.key}
                x={lx}
                y={ly + 4}
                textAnchor="middle"
                fontSize="10"
                fontFamily="var(--mono)"
                fill="var(--text-secondary)"
              >
                {cat.label}
              </text>
            )
          })}
        </svg>
      </div>

      <div className="radar-legend row center mt1" style={{ gap: '1rem', justifyContent: 'center' }}>
        <span className="tiny" style={{ color: 'var(--accent-cyan)' }}>■ {nameA}</span>
        {nameB && facadesB && (
          <span className="tiny" style={{ color: 'var(--accent-lime)' }}>■ {nameB}</span>
        )}
      </div>
    </div>
  )
}
