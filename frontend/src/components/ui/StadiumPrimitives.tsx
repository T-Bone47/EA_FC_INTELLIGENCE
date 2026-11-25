import React from 'react'
import { Link } from 'react-router-dom'
import { StadiumIcon, StadiumIconName } from '../StadiumIcons'

export interface BreadcrumbItem {
  label: string
  to?: string
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  statusPill,
  actions,
}: {
  title: React.ReactNode
  description?: React.ReactNode
  breadcrumbs?: BreadcrumbItem[]
  statusPill?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <header className="st3-page-header">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="st3-breadcrumbs" aria-label="Breadcrumb">
          {breadcrumbs.map((b, i) => (
            <React.Fragment key={`${b.label}-${i}`}>
              {i > 0 && <span className="st3-crumb-sep" aria-hidden="true">/</span>}
              {b.to ? <Link to={b.to}>{b.label}</Link> : <span>{b.label}</span>}
            </React.Fragment>
          ))}
        </nav>
      )}
      <div className="st3-header-main">
        <div className="st3-header-copy">
          <div className="st3-title-row">
            <h1>{title}</h1>
            {statusPill}
          </div>
          {description && <p className="st3-subtitle">{description}</p>}
        </div>
        {actions && <div className="st3-header-actions">{actions}</div>}
      </div>
    </header>
  )
}

export function EpistemicChip({
  kind,
  label,
}: {
  kind: 'observed' | 'modelled' | 'hypothetical' | 'synthetic' | 'frozen' | 'neutral'
  label: string
}) {
  const iconMap: Record<typeof kind, StadiumIconName> = {
    observed: 'check',
    modelled: 'activity',
    hypothetical: 'sliders',
    synthetic: 'alert',
    frozen: 'shield',
    neutral: 'info',
  }
  return (
    <span className={`st3-chip st3-chip-${kind}`}>
      <StadiumIcon name={iconMap[kind]} size={13} />
      <span>{label}</span>
    </span>
  )
}

export function MetricDatum({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: React.ReactNode
  hint?: string
  accent?: 'lime' | 'cyan' | 'warn' | 'bad'
}) {
  return (
    <div className="st3-datum">
      <div className="st3-datum-label">{label}</div>
      <div className={`st3-datum-value ${accent ? `st3-text-${accent}` : ''}`}>{value}</div>
      {hint && <div className="st3-datum-hint">{hint}</div>}
    </div>
  )
}
