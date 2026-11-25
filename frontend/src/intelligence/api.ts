import { api, ApiError } from '../api/client'
import type { CompareResponse, RecommendationOptions, RecommendRequest, RecommendResponse, StatedFootballStyle, WhatIfResponse, WhatIfVariant } from './types'

export const recommendationOptions = () => api.get<RecommendationOptions>('/api/v3/options')

export async function savedFootballStyle(): Promise<StatedFootballStyle | null> {
  const me = await api.get<{ preferences: { football_style?: StatedFootballStyle } | null }>('/api/auth/me')
  return me.preferences?.football_style ?? null
}

/** Thin wrappers: one POST each, response returned untouched (no client-side ranking or scoring). */
export const recommend = (req: RecommendRequest) =>
  api.post<RecommendResponse>('/api/v3/recommendations', req)

export const compare = (request: RecommendRequest, entityIds: string[]) =>
  api.post<CompareResponse>('/api/v3/compare', { request, entity_ids: entityIds })

export const whatIf = (base: RecommendRequest, variants: WhatIfVariant[], trackTop = 10) =>
  api.post<WhatIfResponse>('/api/v3/what-if', { base, variants, track_top: trackTop })

/** Anything thrown while talking to the API, as an ApiError the UI can show (network failures have no status). */
export const toApiError = (e: unknown): ApiError =>
  e instanceof ApiError ? e : new ApiError(0, e instanceof Error ? e.message : String(e))
