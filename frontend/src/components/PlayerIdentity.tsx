export function PlayerIdentity({ name }: { name: string }) {
  const monogram = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map(word => Array.from(word)[0])
    .join('')
    .toUpperCase()

  return (
    <div className="identity-panel" aria-hidden="true">
      <div className="fc-silhouette-avatar">
        {monogram ? (
          <span className="identity-monogram">{monogram}</span>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        )}
      </div>
    </div>
  )
}
