import type { ReactNode } from 'react'
import type { FormationSlot } from '../intelligence/types'

const lane: Record<string, number> = {
  ST: 0, CF: 0, LW: 0, RW: 0,
  CAM: 1, LM: 2, RM: 2, CM: 2, CDM: 3,
  LWB: 3, RWB: 3, LB: 4, RB: 4, CB: 4, GK: 5,
}
const flank: Record<string, number> = { LEFT: -1, CENTER: 0, CENTRE: 0, RIGHT: 1 }

/** Pitch coordinates visualize formation slots supplied by the application. */
export function StadiumPitch({ slots, render }: {
  slots: FormationSlot[]
  render: (slot: FormationSlot) => ReactNode
}) {
  const rows = new Map<number, FormationSlot[]>()
  for (const slot of slots) {
    const row = lane[slot.position] ?? 2
    const players = rows.get(row) ?? []
    rows.set(row, [...players, slot])
  }
  return (
    <div className="stadium-pitch">
      <div className="pitch-markings" aria-hidden="true">
        <i />
        <i />
        <span className="pitch-corner-tl" />
        <span className="pitch-corner-tr" />
        <span className="pitch-corner-bl" />
        <span className="pitch-corner-br" />
      </div>
      {[...rows].sort(([a], [b]) => a - b).map(([row, players]) => (
        <div className="pitch-row" key={row}>
          {[...players].sort((a, b) => (flank[a.side.toUpperCase()] ?? 0) - (flank[b.side.toUpperCase()] ?? 0))
            .map(slot => <div className="pitch-station" key={slot.slot}>{render(slot)}</div>)}
        </div>
      ))}
    </div>
  )
}
