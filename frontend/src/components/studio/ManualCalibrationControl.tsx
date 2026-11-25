import { useState } from 'react'

interface Props {
  videoId: string
  onCalibrated: () => void
}

export function ManualCalibrationControl({ videoId, onCalibrated }: Props) {
  const [open, setOpen] = useState(false)
  const [topLeftU, setTopLeftU] = useState('240')
  const [topLeftV, setTopLeftV] = useState('320')
  const [topRightU, setTopRightU] = useState('1680')
  const [topRightV, setTopRightV] = useState('320')
  const [botRightU, setBotRightU] = useState('1900')
  const [botRightV, setBotRightV] = useState('960')
  const [botLeftU, setBotLeftU] = useState('20')
  const [botLeftV, setBotLeftV] = useState('960')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submitCalibration(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setStatusMsg(null)
    try {
      const res = await fetch(`/api/research/calibration/${videoId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          frame_width: 1920,
          frame_height: 1080,
          landmarks: [
            { name: 'TOP_LEFT_TOUCHLINE', pixel_xy: [Number(topLeftU), Number(topLeftV)], pitch_xy_meters: [0, 68] },
            { name: 'TOP_RIGHT_TOUCHLINE', pixel_xy: [Number(topRightU), Number(topRightV)], pitch_xy_meters: [105, 68] },
            { name: 'BOT_RIGHT_TOUCHLINE', pixel_xy: [Number(botRightU), Number(botRightV)], pitch_xy_meters: [105, 0] },
            { name: 'BOT_LEFT_TOUCHLINE', pixel_xy: [Number(botLeftU), Number(botLeftV)], pitch_xy_meters: [0, 0] },
          ],
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setStatusMsg(
          `Calibrated (${data.calibration.state}, RMSE ${data.calibration.reprojection_error_m.toFixed(2)}m). Re-run perception to apply.`
        )
        onCalibrated()
      } else {
        setStatusMsg('Calibration rejected — verify 4 non-collinear landmarks.')
      }
    } catch {
      setStatusMsg('Failed to reach calibration endpoint.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt03">
      <button type="button" className="btn ghost sm" onClick={() => setOpen(!open)}>
        {open ? 'Hide Manual Pitch Calibration' : 'Manual 4-Point Calibration Fallback'}
      </button>

      {open && (
        <form onSubmit={submitCalibration} className="coaching-diag-card mt02">
          <div className="tiny text-secondary mb02">
            Pin 4 pitch corner pixel coordinates (1920×1080 reference) if broadcast zooms degrade automatic Hough line homography:
          </div>
          <div className="grid-4col gap05 tiny">
            <div>
              <label className="text-muted">Far Left (u, v)</label>
              <div className="row gap02">
                <input className="input sm" value={topLeftU} onChange={e => setTopLeftU(e.target.value)} aria-label="Far left U" />
                <input className="input sm" value={topLeftV} onChange={e => setTopLeftV(e.target.value)} aria-label="Far left V" />
              </div>
            </div>
            <div>
              <label className="text-muted">Far Right (u, v)</label>
              <div className="row gap02">
                <input className="input sm" value={topRightU} onChange={e => setTopRightU(e.target.value)} aria-label="Far right U" />
                <input className="input sm" value={topRightV} onChange={e => setTopRightV(e.target.value)} aria-label="Far right V" />
              </div>
            </div>
            <div>
              <label className="text-muted">Near Right (u, v)</label>
              <div className="row gap02">
                <input className="input sm" value={botRightU} onChange={e => setBotRightU(e.target.value)} aria-label="Near right U" />
                <input className="input sm" value={botRightV} onChange={e => setBotRightV(e.target.value)} aria-label="Near right V" />
              </div>
            </div>
            <div>
              <label className="text-muted">Near Left (u, v)</label>
              <div className="row gap02">
                <input className="input sm" value={botLeftU} onChange={e => setBotLeftU(e.target.value)} aria-label="Near left U" />
                <input className="input sm" value={botLeftV} onChange={e => setBotLeftV(e.target.value)} aria-label="Near left V" />
              </div>
            </div>
          </div>
          <div className="row space-between align-center mt02">
            <button type="submit" className="btn-primary-action sm" disabled={saving}>
              {saving ? 'Computing SVD DLT…' : 'Apply Manual Homography Override'}
            </button>
            {statusMsg && <span className="tiny text-lime">{statusMsg}</span>}
          </div>
        </form>
      )}
    </div>
  )
}
