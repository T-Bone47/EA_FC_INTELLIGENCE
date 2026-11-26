import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { StadiumPitch } from './StadiumPitch'
import { StadiumIcon } from './StadiumIcons'

export function AccountLayout({ children }: { children: ReactNode }) {
  return (
    <div className="account-layout">
      <section className="account-intro">
        <div className="row align-center gap05 mb05">
          <span className="badge lime">Stadium 3.0</span>
          <span className="section-title mb0">Tactical Cockpit</span>
        </div>
        <h2>Your football intelligence, saved.</h2>
        <p className="muted">Keep your tactical preferences, shortlists and squads synchronized across sessions.</p>
        
        <div className="row gap05 wrap mb1">
          <span className="badge outline row align-center gap03" style={{ fontSize: '0.72rem' }}>
            <StadiumIcon name="shield" size={12} /> Strict Data Honesty
          </span>
          <span className="badge outline row align-center gap03" style={{ fontSize: '0.72rem' }}>
            <StadiumIcon name="zap" size={12} /> V3.2.1 Engine
          </span>
          <span className="badge outline row align-center gap03" style={{ fontSize: '0.72rem' }}>
            <StadiumIcon name="squad" size={12} /> Squad Lab Sync
          </span>
        </div>

        <StadiumPitch slots={[]} render={() => null} />
      </section>
      
      <section className="card account-form">
        {children}
        <div className="pt05 border-t">
          <Link className="btn ghost wide" to="/" style={{ textAlign: 'center' }}>
            ← Continue as guest
          </Link>
        </div>
      </section>
    </div>
  )
}
