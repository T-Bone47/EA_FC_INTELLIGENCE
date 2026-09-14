import { describe, expect, it } from 'vitest'
import {
  UNKNOWN_LABEL, age, coins, confidenceLabel, dateShort, isUnknown,
  num, ovrClass, pct, prettyAttr, prettyEnum, score3, text,
} from './format'

describe('UNKNOWN handling — the golden rule of the UI', () => {
  it('treats null/undefined/empty as UNKNOWN', () => {
    expect(isUnknown(null)).toBe(true)
    expect(isUnknown(undefined)).toBe(true)
    expect(isUnknown('')).toBe(true)
    expect(isUnknown(0)).toBe(false)     // zero is a VALUE, not unknown
    expect(isUnknown(false)).toBe(false)
  })

  it('never renders a missing number as 0', () => {
    expect(num(null)).toBe(UNKNOWN_LABEL)
    expect(num(undefined)).toBe(UNKNOWN_LABEL)
    expect(num(0)).toBe('0')
    expect(score3(null)).toBe(UNKNOWN_LABEL)
    expect(pct(null)).toBe(0)            // bar width only — label still UNKNOWN
    expect(text(null)).toBe(UNKNOWN_LABEL)
  })

  it('keeps missing prices UNKNOWN', () => {
    expect(coins(null)).toBe(UNKNOWN_LABEL)
    expect(coins(0)).toBe('0')
    expect(coins(1500)).toBe('1.5k')
    expect(coins(2_300_000)).toBe('2.3M')
  })
})

describe('formatters', () => {
  it('classifies overall ratings', () => {
    expect(ovrClass(91)).toBe('elite')
    expect(ovrClass(84)).toBe('high')
    expect(ovrClass(72)).toBe('mid')
    expect(ovrClass(60)).toBe('low')
    expect(ovrClass(null)).toBe('')
  })

  it('computes age from birth date, UNKNOWN stays null', () => {
    expect(age('1998-12-20', new Date('2026-09-13'))).toBe(27)
    expect(age('1998-12-20', new Date('2026-12-20'))).toBe(28)
    expect(age(null)).toBeNull()
    expect(age('garbage')).toBeNull()
  })

  it('labels confidence bands', () => {
    expect(confidenceLabel(0.9)).toEqual({ label: 'HIGH', cls: 'ok' })
    expect(confidenceLabel(0.6)).toEqual({ label: 'MEDIUM', cls: 'info' })
    expect(confidenceLabel(0.2)).toEqual({ label: 'LOW', cls: 'warn' })
    expect(confidenceLabel(null).label).toBe(UNKNOWN_LABEL)
  })

  it('prettifies attribute codes', () => {
    expect(prettyAttr('gk_diving')).toBe('GK Diving')
    expect(prettyAttr('defensive_awareness')).toBe('Defensive Awareness')
    expect(prettyEnum('COUNTER_ATTACK')).toBe('Counter Attack')
    expect(prettyEnum('INSUFFICIENT_EVIDENCE')).toBe('Insufficient Evidence')
  })

  it('formats dates, UNKNOWN-safe', () => {
    expect(dateShort(null)).toBe(UNKNOWN_LABEL)
    expect(dateShort('2026-03-15')).toMatch(/2026/)
  })
})
