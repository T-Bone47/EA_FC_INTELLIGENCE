import fs from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { pathToFileURL } from 'node:url'
import { scenarios } from './scenarios.mjs'

const required = [
  'A initial state + keyboard', 'flow desktop', 'flow tablet', 'flow mobile',
  'C2 desktop stress', 'C2 tablet stress', 'C2 mobile stress', 'F focus-visibility probe', 'FC27 research flow',
  ...['503 object detail shows the server message', '500 plain error is surfaced, not swallowed',
      'malformed 200 (ranked: null)', 'empty ranked list says so', 'slow response shows a loading indicator',
      'network failure is surfaced'].map(name => 'G ' + name),
]
const requiredShots = ['results_desktop', 'results_tablet', 'results_mobile', 'compare_desktop', 'compare_mobile', 'fc27_desktop']

export async function runQA({ base, out, shots, launch, run, requiredSuites = required, screenshots = requiredShots }) {
  const id = randomUUID()
  const dir = path.join(shots, id)
  const R = { id, timestamp: new Date().toISOString(), base, build: process.env.QA_BUILD || process.env.GITHUB_SHA || 'unversioned export',
    environment: process.platform, node: process.version, browser: null, checks: [], suites: [], screenshots: [],
    layout: [], axe: [], focus: [], touch: [], console: [] }
  let browser, scenario = 'startup'
  const check = (name, ok, detail = '', severity = ok ? 'INFO' : 'FAIL') =>
    R.checks.push({ scenario, name, ok: Boolean(ok), severity, detail: String(detail) })
  const guard = async (name, fn) => {
    scenario = name
    const before = R.checks.length
    try {
      await fn()
      if (R.checks.length === before) throw Error('Required suite produced no assertions')
      R.suites.push(name)
    } catch (error) { check(name, false, error.stack, 'BLOCKER') }
  }
  try {
    if (!['http:', 'https:'].includes(new URL(base).protocol)) throw Error('Invalid QA_BASE')
    fs.mkdirSync(dir, { recursive: true })
    browser = await launch()
    R.browser = await browser.version()
    await run({ browser, R, BASE: base, SHOTS: dir, check, guard })
    for (const name of requiredSuites) {
      if (!R.suites.includes(name)) check(name, false, 'Missing completed suite', 'BLOCKER')
    }
    if (!R.checks.some(c => c.ok)) check('assertions', false, 'No passing assertions')
    for (const name of screenshots) {
      const file = path.join(dir, 'shot_' + name + '.png')
      if (fs.statSync(file).size === 0) throw Error('Empty screenshot ' + file)
      R.screenshots.push(file)
    }
  } catch (error) { check('infrastructure', false, error.stack, 'BLOCKER') }
  finally {
    try { await browser?.close() } catch (error) { check('browser cleanup', false, error.stack, 'BLOCKER') }
    R.exitCode = Number(R.checks.some(c => !c.ok && ['FAIL', 'BLOCKER'].includes(c.severity)))
    R.status = R.exitCode ? 'FAIL' : 'PASS'
    fs.mkdirSync(path.dirname(out), { recursive: true })
    fs.writeFileSync(out, JSON.stringify(R, null, 2))
  }
  return R.exitCode
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await runQA({ base: process.env.QA_BASE ?? 'http://127.0.0.1:4173',
    out: process.env.QA_OUT ?? 'results.json', shots: process.env.QA_SHOTS ?? '.',
    launch: async () => {
      const { default: puppeteer } = await import('puppeteer-core')
      if (process.env.QA_CHROME) return puppeteer.launch({ executablePath: process.env.QA_CHROME, headless: true })
      const { default: chromium } = await import('@sparticuz/chromium')
      return puppeteer.launch({ args: chromium.args, executablePath: await chromium.executablePath(), headless: 'shell' })
    },
    run: async ctx => scenarios({ ...ctx, AXE: fs.readFileSync(new URL(import.meta.resolve('axe-core/axe.min.js')), 'utf8') })
  })
}
