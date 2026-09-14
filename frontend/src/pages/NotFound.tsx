import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div style={{ maxWidth: 560, margin: '4rem auto', textAlign: 'center' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: '3rem', color: 'var(--text-faint)' }}>404</div>
      <h1>Page not found</h1>
      <p className="muted">
        That route does not exist in this app. Nothing was fabricated to fill it.
      </p>
      <div className="row" style={{ justifyContent: 'center' }}>
        <Link className="btn primary" to="/">Home</Link>
        <Link className="btn ghost" to="/search">Player search</Link>
      </div>
    </div>
  )
}
