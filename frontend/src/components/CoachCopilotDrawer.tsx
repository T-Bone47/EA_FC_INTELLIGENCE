import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getToken } from '../api/client'
import { useCopilot } from '../state/copilot'
import { useSession } from '../state/session'
import { ScreenshotRedactorModal, type RedactedScreenshotPayload } from './ScreenshotRedactorModal'
import { StadiumSelect } from './StadiumControls'
import { StadiumIcon } from './StadiumIcons'
import './CoachCopilotDrawer.css'

type ProviderPref = 'AUTO' | 'GEMINI' | 'OPENROUTER_FREE' | 'DETERMINISTIC'

const ROUTE_QUICK_PROMPTS: Record<string, string[]> = {
  PLAYER_DISCOVERY: [
    'Which player in these filters fits my Gamer DNA?',
    'Find undervalued role specialists for a 4-2-3-1',
  ],
  PLAYER_DETAIL: [
    'Does this player fit my tactical profile or create weaknesses?',
    'Who offers safer progression alternatives at this position?',
  ],
  PLAYER_COMPARE: [
    'Compare these selected players against my Gamer DNA',
    'Explain key playstyle and stamina differences for late game',
  ],
  SQUAD_LAB: [
    'Audit this squad for weak slots and rest-defense risk',
    'Propose an upgrade keeping chemistry and role fit high',
  ],
  TACTICAL_LAB: [
    'Compare Arm A vs Arm B in my active tactical experiment',
    'What is my nominal vs observed in/out-of-possession shape?',
    'Should I change tactics or replace my CDM before spending coins?',
  ],
  GAMEPLAY_STUDIO: [
    'What caused my recent transition losses in this footage?',
    'How do I correct the spatial gap shown at this timestamp?',
  ],
  DECISION_LAB: [
    'Why does the counterfactual prefer the alternative option here?',
    'How close is the regret margin relative to interception risk?',
  ],
  GAMER_DNA: [
    'Summarize my biggest recurring tactical habit to fix next match',
    'Which category in Training Academy matches my weakest match trend?',
  ],
  GENERAL: [
    'What is my top tactical improvement priority right now?',
    'Explain EA FC 27 FC IQ Holding vs Deep-Lying Playmaker roles',
  ],
}

export function CoachCopilotDrawer() {
  const { user, gameVersion, notify } = useSession()
  const {
    isOpen,
    closeCopilot,
    contextEnvelope,
    queuedPrompt,
    clearQueuedPrompt,
    sessionId,
    setSessionId,
  } = useCopilot()

  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [statusLabel, setStatusLabel] = useState('')
  const [streamPreview, setStreamPreview] = useState('')
  const [providerPref, setProviderPref] = useState<ProviderPref>('AUTO')
  const [consentExternal, setConsentExternal] = useState(false)
  const [prefsLoaded, setPrefsLoaded] = useState(false)
  const [responses, setResponses] = useState<{ q: string; r: Record<string, any> }[]>([])
  const [showRedactor, setShowRedactor] = useState(false)
  const [attachedScreenshot, setAttachedScreenshot] = useState<RedactedScreenshotPayload | null>(null)
  const [proposalStates, setProposalStates] = useState<Record<string, string>>({})

  const abortRef = useRef<AbortController | null>(null)
  const activeReqIdRef = useRef<string | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const timer = window.setTimeout(() => inputRef.current?.focus(), 60)
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !showRedactor) {
        closeCopilot()
      }
    }
    window.addEventListener('keydown', onEsc)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('keydown', onEsc)
    }
  }, [isOpen, showRedactor, closeCopilot])

  useEffect(() => {
    if (!user || !isOpen || prefsLoaded) return
    api
      .get<{ preferred_provider?: ProviderPref; consent_external_llm?: boolean }>('/api/phase40/coach/preferences')
      .then(prefs => {
        if (prefs.preferred_provider) setProviderPref(prefs.preferred_provider)
        if (typeof prefs.consent_external_llm === 'boolean') setConsentExternal(prefs.consent_external_llm)
        setPrefsLoaded(true)
      })
      .catch(() => setPrefsLoaded(true))
  }, [user, isOpen, prefsLoaded])

  useEffect(() => {
    if (!isOpen || !queuedPrompt) return
    const nextPrompt = queuedPrompt
    clearQueuedPrompt()
    setQuestion(nextPrompt)
    if (user) {
      submitQuestion(nextPrompt)
    }
  }, [isOpen, queuedPrompt, user])

  async function savePreferences() {
    if (!user) return
    try {
      await api.put('/api/phase40/coach/preferences', {
        preferred_provider: providerPref,
        consent_external_llm: consentExternal,
        preferred_formation: contextEnvelope.active_formation || '4-2-3-1',
        preferred_tactical_profile: contextEnvelope.active_tactical_profile || 'BALANCED',
      })
      notify('ok', 'Co-Pilot preferences saved.')
    } catch {
      notify('bad', 'Could not save preferences.')
    }
  }

  async function stopStream() {
    abortRef.current?.abort()
    if (activeReqIdRef.current) {
      await api.post(`/api/phase40/coach/cancel/${encodeURIComponent(activeReqIdRef.current)}`).catch(() => {})
    }
    setAsking(false)
    setStatusLabel('Cancelled.')
  }

  async function submitQuestion(textToAsk: string) {
    const trimmed = textToAsk.trim()
    if (!trimmed || !user) return
    const reqId = `copilot-${Date.now()}`
    activeReqIdRef.current = reqId
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setAsking(true)
    setStreamPreview('')
    setStatusLabel('Validating context & connecting…')

    const payload: Record<string, any> = {
      question: trimmed,
      session_id: sessionId,
      game_version: gameVersion === 'FC26' ? 'FC26' : 'FC27',
      squad_id: contextEnvelope.squad_id || null,
      active_match_id: contextEnvelope.match_id || null,
      context_envelope: {
        ...contextEnvelope,
        source_route: contextEnvelope.route_name || 'GENERAL',
      },
      consent_external_llm: consentExternal,
      preferred_provider: providerPref,
      request_id: reqId,
    }
    if (attachedScreenshot) {
      payload.user_consent_media = attachedScreenshot.consentMedia
      payload.redaction_confirmed = attachedScreenshot.redactionConfirmed
      payload.screenshot_use_case = attachedScreenshot.useCase
      payload.image_b64 = attachedScreenshot.imageB64
      payload.image_mime = attachedScreenshot.mime
    }

    try {
      const token = getToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch('/api/phase40/coach/ask/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      })

      if (res.ok && res.body && res.headers.get('content-type')?.includes('text/event-stream')) {
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        let finalResp: Record<string, any> | null = null
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const blocks = buf.split('\n\n')
          buf = blocks.pop() || ''
          for (const blk of blocks) {
            const evLine = blk.split('\n').find(l => l.startsWith('event:'))
            const dataLine = blk.split('\n').find(l => l.startsWith('data:'))
            if (!dataLine) continue
            const evName = evLine ? evLine.slice(6).trim() : 'message'
            const parsed = JSON.parse(dataLine.slice(5).trim())
            if (evName === 'stage') {
              setStatusLabel(`Stage: ${parsed.stage}`)
            } else if (evName === 'tool_start') {
              setStatusLabel(`Running: ${(parsed.tools || []).join(', ')}`)
            } else if (evName === 'delta') {
              setStreamPreview(prev => prev + (parsed.text || ''))
            } else if (evName === 'done') {
              finalResp = parsed
            }
          }
        }
        if (finalResp) {
          setSessionId(finalResp.session_id)
          setResponses(prev => [{ q: trimmed, r: finalResp! }, ...prev])
          setQuestion('')
          setAttachedScreenshot(null)
          return
        }
      }

      const fallbackRes = await api.post<Record<string, any>>('/api/phase40/coach/ask', payload)
      setSessionId(fallbackRes.session_id)
      setResponses(prev => [{ q: trimmed, r: fallbackRes }, ...prev])
      setQuestion('')
      setAttachedScreenshot(null)
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        notify('bad', err?.detail || 'Co-Pilot request failed.')
      }
    } finally {
      setAsking(false)
      setStreamPreview('')
      setStatusLabel('')
      activeReqIdRef.current = null
    }
  }

  async function handleConfirmProposal(pid: string) {
    try {
      await api.post(`/api/phase40/squad-proposals/${pid}/confirm`, {})
      setProposalStates(s => ({ ...s, [pid]: 'CONFIRMED' }))
      notify('ok', 'Squad proposal confirmed.')
    } catch (e: any) {
      notify('bad', e?.detail || 'Confirmation failed.')
    }
  }

  async function handleRollbackProposal(pid: string) {
    try {
      await api.post(`/api/phase40/squad-proposals/${pid}/rollback`, {})
      setProposalStates(s => ({ ...s, [pid]: 'ROLLED_BACK' }))
      notify('info', 'Squad change rolled back.')
    } catch (e: any) {
      notify('bad', e?.detail || 'Rollback failed.')
    }
  }

  if (!isOpen) return null

  const quickPrompts = ROUTE_QUICK_PROMPTS[contextEnvelope.route_name] || ROUTE_QUICK_PROMPTS.GENERAL

  return (
    <div
      className="copilot-drawer-backdrop"
      role="presentation"
      onClick={e => {
        if (e.target === e.currentTarget && !showRedactor) closeCopilot()
      }}
    >
      <aside className="copilot-drawer" role="dialog" aria-modal="true" aria-label="EA FC Intelligence Co-Pilot">
        <header className="copilot-drawer-head">
          <div className="row space-between align-center">
            <div className="row gap04 align-center">
              <StadiumIcon name="coach" size={16} />
              <strong className="text-white">Tactical Co-Pilot</strong>
              <span className="badge sm lime font-mono">{contextEnvelope.game_version}</span>
            </div>
            <div className="row gap04 align-center">
              <Link className="btn ghost sm" to="/coach" onClick={closeCopilot}>Full Lab</Link>
              <button type="button" className="btn ghost sm" onClick={closeCopilot} aria-label="Close Co-Pilot">Close</button>
            </div>
          </div>

          <div className="copilot-context-bar tiny">
            <span className="badge sm cyan font-mono">{contextEnvelope.route_name}</span>
            {contextEnvelope.squad_id && <span className="badge sm outline font-mono">Squad linked</span>}
            {contextEnvelope.decision_id && <span className="badge sm outline font-mono">Decision linked</span>}
            {contextEnvelope.tactical_snapshot_id && <span className="badge sm outline font-mono">Snapshot linked</span>}
            {contextEnvelope.experiment_id && <span className="badge sm outline font-mono">Experiment linked</span>}
            {contextEnvelope.selected_card_ids?.length ? (
              <span className="badge sm outline font-mono">{contextEnvelope.selected_card_ids.length} player(s)</span>
            ) : null}
            {contextEnvelope.active_filters && Object.entries(contextEnvelope.active_filters).some(([k, v]) => k !== 'selection_mode' && v) && (
              <span className="badge sm outline font-mono">Filters active</span>
            )}
            {typeof contextEnvelope.visible_timestamp_sec === 'number' && (
              <span className="badge sm outline font-mono">@{contextEnvelope.visible_timestamp_sec.toFixed(1)}s</span>
            )}
          </div>
        </header>

        <div className="copilot-body">
          {!user ? (
            <div className="callout info small">
              <strong>Sign in required for personal tools:</strong>{' '}
              <Link to="/login" onClick={closeCopilot}>Log in</Link> or <Link to="/signup" onClick={closeCopilot}>Sign up</Link> to query your Gamer DNA, saved squads, Decision Lab windows, or redacted screenshots.
            </div>
          ) : (
            <>
              <div className="copilot-prompt-chips">
                {quickPrompts.map(qText => (
                  <button
                    key={qText}
                    type="button"
                    className="copilot-chip-btn"
                    onClick={() => submitQuestion(qText)}
                    disabled={asking}
                  >
                    {qText}
                  </button>
                ))}
              </div>

              {asking && (
                <div className="copilot-msg-card">
                  <div className="tiny text-lime font-mono">{statusLabel || 'Working…'}</div>
                  {streamPreview && <p className="tiny text-white mb0">{streamPreview}</p>}
                </div>
              )}

              {responses.map(({ q, r }) => (
                <article key={r.message_id || q} className="copilot-msg-card">
                  <div className="tiny text-muted strong">You: {q}</div>
                  <div className="row gap03 flex-wrap tiny">
                    <span className="badge sm outline font-mono">{r.provider}:{r.model}</span>
                    {r.ttft_ms ? <span className="badge sm outline font-mono">TTFT {Math.round(r.ttft_ms)}ms</span> : null}
                    {r.latency_ms ? <span className="badge sm outline font-mono">{Math.round(r.latency_ms)}ms</span> : null}
                  </div>
                  <p className="small text-white mb0">{r.answer}</p>

                  {Array.isArray(r.multimodal_candidate_notes) && r.multimodal_candidate_notes.length > 0 && (
                    <div className="callout warn tiny mb0">
                      <strong>Unverified Screenshot Observation:</strong> {r.multimodal_candidate_notes.join(' ')}
                    </div>
                  )}

                  {Array.isArray(r.player_cards) && r.player_cards.length > 0 && (
                    <div className="stack gap02">
                      {r.player_cards.slice(0, 4).map((card: any) => (
                        <Link
                          key={card.id || card.name}
                          to={`/players/${encodeURIComponent(card.id || '')}?game_version=${encodeURIComponent(card.game_version || gameVersion)}`}
                          onClick={closeCopilot}
                          className="coach-option-btn tiny row space-between"
                        >
                          <span><strong>{card.name}</strong> ({card.position || '—'} · {card.ovr ?? '—'})</span>
                          <span className="font-mono text-lime">{card.verdict_label || 'Inspect →'}</span>
                        </Link>
                      ))}
                    </div>
                  )}

                  {r.squad_proposal && (
                    <div className="callout info tiny">
                      <strong>Pending Squad Proposal ({r.squad_proposal.target_slot}):</strong> {r.squad_proposal.summary}
                      <div className="row gap04 mt03">
                        <button
                          type="button"
                          className="btn primary sm"
                          disabled={proposalStates[r.squad_proposal.proposal_id] === 'CONFIRMED'}
                          onClick={() => handleConfirmProposal(r.squad_proposal.proposal_id)}
                        >
                          {proposalStates[r.squad_proposal.proposal_id] === 'CONFIRMED' ? 'Confirmed' : 'Confirm'}
                        </button>
                        <button
                          type="button"
                          className="btn ghost sm"
                          onClick={() => handleRollbackProposal(r.squad_proposal.proposal_id)}
                        >
                          Rollback
                        </button>
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </>
          )}
        </div>

        <footer className="copilot-composer">
          <div className="row space-between align-center flex-wrap gap04 tiny">
            <div style={{ minWidth: 185, flex: '1 1 185px' }}>
              <StadiumSelect
                aria-label="Co-Pilot Provider"
                value={providerPref}
                onChange={val => setProviderPref(val as ProviderPref)}
              >
                <option value="AUTO">Auto (Gemini → Det.)</option>
                <option value="GEMINI">Gemini Free</option>
                <option value="OPENROUTER_FREE">OpenRouter Free</option>
                <option value="DETERMINISTIC">Deterministic Only</option>
              </StadiumSelect>
            </div>
            <label className="checkbox tiny">
              <input type="checkbox" checked={consentExternal} onChange={e => setConsentExternal(e.target.checked)} />
              <span>External AI opt-in</span>
            </label>
            {user && (
              <button type="button" className="btn ghost sm" onClick={savePreferences}>Save Prefs</button>
            )}
          </div>
          {providerPref !== 'DETERMINISTIC' && !consentExternal && (
            <div className="tiny text-muted" role="note">
              External AI opt-in is unchecked — provider {providerPref} will not be called and grounded Deterministic Coach will answer locally.
            </div>
          )}

          <div className="row gap04 align-center">
            <button
              type="button"
              className="btn ghost sm"
              disabled={!user}
              onClick={() => setShowRedactor(true)}
            >
              {attachedScreenshot ? `Redacted Img (${attachedScreenshot.redactionCount})` : 'Attach Screenshot'}
            </button>
            {attachedScreenshot && (
              <button type="button" className="btn ghost sm" onClick={() => setAttachedScreenshot(null)}>Clear Img</button>
            )}
          </div>

          <form
            className="row gap04"
            onSubmit={e => {
              e.preventDefault()
              submitQuestion(question)
            }}
          >
            <input
              ref={inputRef}
              type="text"
              style={{ flex: 1 }}
              value={question}
              disabled={!user}
              onChange={e => setQuestion(e.target.value)}
              placeholder={user ? 'Ask Co-Pilot about this view… (Ctrl+Shift+C)' : 'Sign in to use Co-Pilot'}
              aria-label="Ask Co-Pilot"
            />
            {asking ? (
              <button type="button" className="btn ghost sm" onClick={stopStream}>Stop</button>
            ) : (
              <button type="submit" className="btn primary sm" disabled={!user || !question.trim()}>Ask</button>
            )}
          </form>
        </footer>
      </aside>

      {showRedactor && (
        <ScreenshotRedactorModal
          onCancel={() => setShowRedactor(false)}
          onAttach={payload => {
            setAttachedScreenshot(payload)
            setShowRedactor(false)
            notify('ok', 'Locally redacted screenshot attached.')
          }}
        />
      )}
    </div>
  )
}
