import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type CopilotRouteName =
  | 'PLAYER_DISCOVERY'
  | 'PLAYER_DETAIL'
  | 'PLAYER_COMPARE'
  | 'SQUAD_LAB'
  | 'GAMEPLAY_STUDIO'
  | 'DECISION_LAB'
  | 'GAMER_DNA'
  | 'GENERAL'

export interface CoachContextEnvelope {
  route_name: CopilotRouteName
  game_version: 'FC26' | 'FC27'
  squad_id?: string | null
  match_id?: string | null
  video_id?: string | null
  decision_id?: string | null
  selected_card_ids?: string[]
  selected_player_names?: string[]
  active_formation?: string | null
  active_tactical_profile?: string | null
  active_filters?: Record<string, unknown>
  visible_timestamp_sec?: number | null
}

interface CopilotState {
  isOpen: boolean
  contextEnvelope: CoachContextEnvelope
  queuedPrompt: string | null
  sessionId: string | null
  openCopilot: (opts?: { prompt?: string; contextOverride?: Partial<CoachContextEnvelope> }) => void
  closeCopilot: () => void
  toggleCopilot: () => void
  setRouteContext: (env: CoachContextEnvelope) => void
  clearQueuedPrompt: () => void
  setSessionId: (sid: string | null) => void
}

const DEFAULT_ENV: CoachContextEnvelope = {
  route_name: 'GENERAL',
  game_version: 'FC27',
}

const CopilotContext = createContext<CopilotState | null>(null)

export function CopilotProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)
  const [contextEnvelope, setContextEnvelope] = useState<CoachContextEnvelope>(DEFAULT_ENV)
  const [queuedPrompt, setQueuedPrompt] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  const openCopilot = useCallback(
    (opts?: { prompt?: string; contextOverride?: Partial<CoachContextEnvelope> }) => {
      if (opts?.contextOverride) {
        setContextEnvelope(prev => ({ ...prev, ...opts.contextOverride }))
      }
      if (opts?.prompt) {
        setQueuedPrompt(opts.prompt)
      }
      setIsOpen(true)
    },
    []
  )

  const closeCopilot = useCallback(() => setIsOpen(false), [])
  const toggleCopilot = useCallback(() => setIsOpen(prev => !prev), [])
  const setRouteContext = useCallback((env: CoachContextEnvelope) => {
    setContextEnvelope(prev => {
      if (JSON.stringify(prev) === JSON.stringify(env)) return prev
      return env
    })
  }, [])
  const clearQueuedPrompt = useCallback(() => setQueuedPrompt(null), [])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'c') {
        e.preventDefault()
        setIsOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <CopilotContext.Provider
      value={{
        isOpen,
        contextEnvelope,
        queuedPrompt,
        sessionId,
        openCopilot,
        closeCopilot,
        toggleCopilot,
        setRouteContext,
        clearQueuedPrompt,
        setSessionId,
      }}
    >
      {children}
    </CopilotContext.Provider>
  )
}

export function useCopilot(): CopilotState {
  const ctx = useContext(CopilotContext)
  if (!ctx) {
    return {
      isOpen: false,
      contextEnvelope: DEFAULT_ENV,
      queuedPrompt: null,
      sessionId: null,
      openCopilot: () => {},
      closeCopilot: () => {},
      toggleCopilot: () => {},
      setRouteContext: () => {},
      clearQueuedPrompt: () => {},
      setSessionId: () => {},
    }
  }
  return ctx
}

export function useCopilotRouteContext(envelope: CoachContextEnvelope) {
  const { setRouteContext } = useCopilot()
  const serialized = JSON.stringify(envelope)
  useEffect(() => {
    setRouteContext(JSON.parse(serialized) as CoachContextEnvelope)
  }, [serialized, setRouteContext])
}
