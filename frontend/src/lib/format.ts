/** Display helpers. The golden rule of this UI: a null/undefined value is
 *  rendered as UNKNOWN — never as 0, never as an empty string that could be
 *  mistaken for "none". */

export const UNKNOWN_LABEL = 'UNKNOWN'

export function isUnknown(v: unknown): boolean {
  return v === null || v === undefined || v === ''
}

/** Numeric-or-UNKNOWN formatter. */
export function num(v: number | null | undefined, digits = 0): string {
  if (isUnknown(v)) return UNKNOWN_LABEL
  return (v as number).toFixed(digits)
}

export function score3(v: number | null | undefined): string {
  if (isUnknown(v)) return UNKNOWN_LABEL
  return (v as number).toFixed(3)
}

export function pct(v: number | null | undefined): number {
  if (isUnknown(v)) return 0
  return Math.round((v as number) * 100)
}

export function text(v: string | null | undefined): string {
  return isUnknown(v) ? UNKNOWN_LABEL : String(v)
}

export function coins(v: number | null | undefined): string {
  if (isUnknown(v)) return UNKNOWN_LABEL
  const n = v as number
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}k`
  return String(n)
}

export function ovrClass(v: number | null | undefined): string {
  if (isUnknown(v)) return ''
  const n = v as number
  if (n >= 87) return 'elite'
  if (n >= 80) return 'high'
  if (n >= 70) return 'mid'
  return 'low'
}

export function prettyAttr(code: string): string {
  return code
    .replace(/^gk_/, 'GK ')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase())
    .replace(/Gk\b/, 'GK')
}

export function prettyEnum(v: string): string {
  return v.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (m) => m.toUpperCase())
}

export function dateShort(iso: string | null | undefined): string {
  if (isUnknown(iso)) return UNKNOWN_LABEL
  const d = new Date(iso as string)
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function dateTime(iso: string | null | undefined): string {
  if (isUnknown(iso)) return UNKNOWN_LABEL
  const d = new Date(iso as string)
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** Age from a birth date string; UNKNOWN stays UNKNOWN. */
export function age(dob: string | null | undefined, now = new Date()): number | null {
  if (isUnknown(dob)) return null
  const b = new Date(dob as string)
  if (Number.isNaN(b.getTime())) return null
  let a = now.getFullYear() - b.getFullYear()
  const m = now.getMonth() - b.getMonth()
  if (m < 0 || (m === 0 && now.getDate() < b.getDate())) a--
  return a
}

export function confidenceLabel(score: number | null | undefined): { label: string; cls: string } {
  if (isUnknown(score)) return { label: UNKNOWN_LABEL, cls: 'unknown' }
  const s = score as number
  if (s >= 0.8) return { label: 'HIGH', cls: 'ok' }
  if (s >= 0.55) return { label: 'MEDIUM', cls: 'info' }
  return { label: 'LOW', cls: 'warn' }
}

export const FACADES = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physicality'] as const
export const FACADE_LABELS: Record<string, string> = {
  pace: 'PAC', shooting: 'SHO', passing: 'PAS',
  dribbling: 'DRI', defending: 'DEF', physicality: 'PHY',
}
