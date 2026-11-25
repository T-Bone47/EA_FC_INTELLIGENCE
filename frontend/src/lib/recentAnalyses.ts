type Analysis = { version: string; position: string; tactic: string; formation?: string; slot?: string; completed: number }
const key = (scope: string) => 'eafc.analyses.' + scope

export function recentAnalyses(scope: string): Analysis[] {
  try {
    const records = JSON.parse(sessionStorage.getItem(key(scope)) ?? '[]')
    return Array.isArray(records) ? records.filter(row => row && typeof row.completed === 'number' &&
      typeof row.version === 'string' && typeof row.position === 'string' && typeof row.tactic === 'string') : []
  } catch {
    return []
  }
}

export function recordAnalysis(scope: string, analysis: Omit<Analysis, 'completed'>) {
  try {
    sessionStorage.setItem(key(scope), JSON.stringify([{ ...analysis, completed: Date.now() }, ...recentAnalyses(scope)].slice(0, 5)))
  } catch { /* Analysis still succeeds when browser storage is unavailable. */ }
}
