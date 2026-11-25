/// <reference types="vite/client" />
import { describe, expect, it } from 'vitest'

// The UI renders the backend's order and numbers. It must never sort, reverse or re-score results.
const sources = import.meta.glob('./*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>

describe('no frontend-side ranking', () => {
  const files = Object.entries(sources).filter(([f]) => !/\.test\.tsx?$/.test(f))

  it('covers the intelligence sources', () => {
    expect(files.length).toBeGreaterThanOrEqual(5)
  })

  it('no intelligence source file sorts or reverses', () => {
    for (const [f, src] of files) expect(src, f).not.toMatch(/\.(sort|toSorted|reverse)\(/)
  })
})
