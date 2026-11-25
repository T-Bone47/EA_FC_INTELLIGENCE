interface TacticalPreviewProps {
  formation?: string
  slot?: string
  tacticalStyle?: string
  slots?: Array<{ slot: string; position: string; duty: string }>
}

export function TacticalPreview({ formation, slot, tacticalStyle, slots = [] }: TacticalPreviewProps) {
  if (!formation && !slot) {
    return (
      <div className="tactical-preview-empty small muted">
        <span>Select a formation or slot above to view tactical alignment on the pitch.</span>
      </div>
    )
  }

  return (
    <div className="tactical-preview-box" aria-label="Formation tactical preview">
      <div className="row space-between align-center mb05">
        <span className="tiny faint font-mono">FORMATION TACTICAL CONTEXT</span>
        <span className="badge info">{formation || 'Standalone'}</span>
      </div>

      <div className="tactical-preview-mini-pitch" aria-hidden="true">
        <div className="mini-pitch-circle" />
        <div className="mini-pitch-half" />
        <div className="mini-pitch-slots">
          {slots.length > 0 ? (
            slots.map((s) => {
              const isSelected = s.slot === slot
              return (
                <div
                  key={s.slot}
                  className={`mini-slot-node ${isSelected ? 'is-selected' : ''}`}
                  title={`${s.slot} (${s.position}) - ${s.duty}`}
                >
                  <span className="mini-slot-label">{s.slot}</span>
                </div>
              )
            })
          ) : (
            <div className="mini-slot-node is-selected" style={{ margin: 'auto' }}>
              <span className="mini-slot-label">{slot || 'POS'}</span>
            </div>
          )}
        </div>
      </div>

      <div className="tactical-preview-meta small mt05">
        <p className="mb0">
          Targeting <strong>{slot || 'selected position'}</strong> under <strong>{tacticalStyle?.replace(/_/g, ' ').toLowerCase() || 'balanced'}</strong> style.
        </p>
      </div>
    </div>
  )
}
