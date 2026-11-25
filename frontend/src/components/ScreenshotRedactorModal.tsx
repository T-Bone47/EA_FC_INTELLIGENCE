import { useEffect, useRef, useState } from 'react'

export type ScreenshotUseCase =
  | 'FORMATION_SCREENSHOT'
  | 'SQUAD_SCREENSHOT'
  | 'MATCH_STATS'
  | 'TACTICAL_FREEZE'
  | 'GAMEPLAY_SITUATION'

interface RectBox {
  x: number
  y: number
  w: number
  h: number
}

export interface RedactedScreenshotPayload {
  imageB64: string
  mime: string
  useCase: ScreenshotUseCase
  redactionCount: number
  redactionConfirmed: boolean
  consentMedia: boolean
}

export function ScreenshotRedactorModal({
  onCancel,
  onAttach,
}: {
  onCancel: () => void
  onAttach: (payload: RedactedScreenshotPayload) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [boxes, setBoxes] = useState<RectBox[]>([])
  const [draggingStart, setDraggingStart] = useState<{ x: number; y: number } | null>(null)
  const [previewBox, setPreviewBox] = useState<RectBox | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [useCase, setUseCase] = useState<ScreenshotUseCase>('FORMATION_SCREENSHOT')
  const [redactionConfirmed, setRedactionConfirmed] = useState(false)
  const [consentMedia, setConsentMedia] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  function redraw(activeBoxes: RectBox[], tempBox: RectBox | null = null) {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#05080f'
    for (const b of activeBoxes) {
      ctx.fillRect(b.x, b.y, b.w, b.h)
    }
    if (tempBox) {
      ctx.fillStyle = 'rgba(184, 245, 122, 0.45)'
      ctx.fillRect(tempBox.x, tempBox.y, tempBox.w, tempBox.h)
      ctx.strokeStyle = '#b8f57a'
      ctx.lineWidth = 2
      ctx.strokeRect(tempBox.x, tempBox.y, tempBox.w, tempBox.h)
    }
  }

  useEffect(() => {
    redraw(boxes, previewBox)
  }, [boxes, previewBox, loaded])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setErrorMsg(null)
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 6 * 1024 * 1024) {
      setErrorMsg('Screenshot file exceeds 6MB limit.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        const canvas = canvasRef.current
        if (!canvas) return
        const maxW = 720
        const scale = Math.min(1, maxW / img.width)
        canvas.width = Math.max(160, Math.round(img.width * scale))
        canvas.height = Math.max(120, Math.round(img.height * scale))
        imgRef.current = img
        setBoxes([])
        setLoaded(true)
      }
      img.src = String(reader.result || '')
    }
    reader.readAsDataURL(file)
  }

  function applyQuickMaskHUD() {
    const c = canvasRef.current
    if (!c) return
    // Masks standard EA FC top-left/top-right user handle & coin balance corners
    setBoxes(prev => [
      ...prev,
      { x: 0, y: 0, w: Math.round(c.width * 0.28), h: Math.round(c.height * 0.11) },
      { x: Math.round(c.width * 0.72), y: 0, w: Math.round(c.width * 0.28), h: Math.round(c.height * 0.11) },
    ])
  }

  function canvasCoords(e: React.MouseEvent<HTMLCanvasElement>) {
    const c = canvasRef.current
    if (!c) return { x: 0, y: 0 }
    const rect = c.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * c.width,
      y: ((e.clientY - rect.top) / rect.height) * c.height,
    }
  }

  function handleAttach() {
    const c = canvasRef.current
    if (!c || !loaded) {
      setErrorMsg('Upload a screenshot image first.')
      return
    }
    if (!redactionConfirmed || !consentMedia) {
      setErrorMsg('Confirm local redaction and explicit media send consent first.')
      return
    }
    // Re-exporting through HTML5 Canvas strips EXIF metadata cleanly
    const dataUrl = c.toDataURL('image/jpeg', 0.86)
    const b64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl
    onAttach({
      imageB64: b64,
      mime: 'image/jpeg',
      useCase,
      redactionCount: boxes.length,
      redactionConfirmed: true,
      consentMedia: true,
    })
  }

  return (
    <div
      className="copilot-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Screenshot Privacy Redaction Canvas"
    >
      <div className="copilot-modal card">
        <div className="row space-between align-center mb05">
          <div>
            <h3 className="section-title mb0">Local Screenshot Privacy Redaction</h3>
            <p className="tiny text-muted mb0">
              Drag black boxes over your gamertag, PSN/EA ID, club name, or coin balance before sending.
            </p>
          </div>
          <button type="button" className="btn ghost sm" onClick={onCancel}>Close</button>
        </div>

        <div className="row gap05 flex-wrap align-center mb05">
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={handleFileChange} aria-label="Choose screenshot image" />
          <select value={useCase} onChange={e => setUseCase(e.target.value as ScreenshotUseCase)} aria-label="Screenshot task type">
            <option value="FORMATION_SCREENSHOT">Formation / Tactics Screen</option>
            <option value="SQUAD_SCREENSHOT">Squad / Lineup Screen</option>
            <option value="MATCH_STATS">Post-Match Statistics</option>
            <option value="TACTICAL_FREEZE">Gameplay Tactical Freeze</option>
            <option value="GAMEPLAY_SITUATION">In-Match Scenario</option>
          </select>
          {loaded && (
            <>
              <button type="button" className="btn ghost sm" onClick={applyQuickMaskHUD}>Mask Top Corners</button>
              <button type="button" className="btn ghost sm" onClick={() => setBoxes(b => b.slice(0, -1))} disabled={boxes.length === 0}>Undo Box</button>
            </>
          )}
        </div>

        <div className="copilot-canvas-wrap">
          <canvas
            ref={canvasRef}
            width={640}
            height={360}
            className="copilot-redact-canvas"
            onMouseDown={e => {
              if (!loaded) return
              setDraggingStart(canvasCoords(e))
            }}
            onMouseMove={e => {
              if (!draggingStart) return
              const cur = canvasCoords(e)
              setPreviewBox({
                x: Math.min(draggingStart.x, cur.x),
                y: Math.min(draggingStart.y, cur.y),
                w: Math.abs(cur.x - draggingStart.x),
                h: Math.abs(cur.y - draggingStart.y),
              })
            }}
            onMouseUp={() => {
              if (previewBox && previewBox.w > 4 && previewBox.h > 4) {
                setBoxes(prev => [...prev, previewBox])
              }
              setDraggingStart(null)
              setPreviewBox(null)
            }}
          />
          {!loaded && (
            <div className="copilot-canvas-placeholder tiny text-muted">
              Select a PNG/JPG screenshot to paint black redaction boxes locally in-browser (EXIF stripped on export).
            </div>
          )}
        </div>

        <div className="stack gap03 mt05 tiny">
          <label className="checkbox">
            <input type="checkbox" checked={redactionConfirmed} onChange={e => setRedactionConfirmed(e.target.checked)} />
            <span>I confirm gamertags/PII have been locally redacted ({boxes.length} mask box(es) applied).</span>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={consentMedia} onChange={e => setConsentMedia(e.target.checked)} />
            <span>Explicit opt-in: send this redacted image for unverified candidate AI observation (kept separate from Gamer DNA).</span>
          </label>
        </div>

        {errorMsg && <p className="tiny text-danger mt04 mb0">{errorMsg}</p>}

        <div className="row space-between align-center mt05">
          <span className="tiny text-muted">Observations tagged CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED</span>
          <div className="row gap05">
            <button type="button" className="btn ghost sm" onClick={onCancel}>Cancel</button>
            <button
              type="button"
              className="btn primary sm"
              disabled={!loaded || !redactionConfirmed || !consentMedia}
              onClick={handleAttach}
            >
              Attach Redacted Screenshot
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
