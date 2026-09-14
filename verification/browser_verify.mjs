// POST-BUILD VERIFICATION — browser-level checks (audit section 10).
// Loads the PRODUCTION build served by FastAPI on :8000, captures console
// errors / uncaught exceptions, and asserts real rendering + data honesty.
// Usage: node verification/browser_verify.mjs [BASE_URL]
import { chromium } from 'playwright'

const BASE = (process.argv[2] || 'http://localhost:8000').replace(/\/$/, '')
const results = []
function check(name, ok, detail) {
  results.push({ name, ok, detail })
  console.log(`[${ok ? 'PASS' : 'FAIL'}] 10-FRONTEND: ${name} — ${detail}`)
}

const browser = await chromium.launch({ args: ['--no-sandbox'] })
const ctx = await browser.newContext()
const page = await ctx.newPage()

const consoleErrors = []
const pageErrors = []
page.on('console', (m) => {
  if (m.type() === 'error') {
    const t = m.text()
    // Expected honest 4xx responses (FC27 NO_DATA, 404s) are not JS failures
    if (/Failed to load resource.*(404|401|403|422|429)/.test(t)) return
    // Vite's HMR websocket is DEV TOOLING, not product code: when the dev server
    // runs behind the sandbox preview proxy (wss :443), direct localhost audits
    // see a refused ws handshake. Only excluded on the dev origin.
    if (BASE.includes(':5173') && /WebSocket connection|ERR_CONNECTION_REFUSED|Failed to load resource/.test(t)) return
    consoleErrors.push(t)
  }
})
page.on('pageerror', (e) => pageErrors.push(String(e)))

// ---------------------------------------------------------------- landing
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
const h1 = await page.locator('h1').first().innerText()
check('landing renders hero', h1.toLowerCase().includes('player quality'), `h1="${h1}"`)
const stats = await page.locator('.stat .n').allInnerTexts()
check('landing shows real counts', stats.some((s) => s.includes('16,228')),
  `stats=${JSON.stringify(stats)}`)

// ---------------------------------------------------------------- search
await page.goto(BASE + '/search?q=valverde', { waitUntil: 'networkidle' })
await page.waitForSelector('table.data tbody tr', { timeout: 10000 })
const rows = await page.locator('table.data tbody tr').count()
const firstRow = await page.locator('table.data tbody tr').first().innerText()
check('search renders results from URL param', rows >= 1 && /Valverde/i.test(firstRow),
  `rows=${rows} first="${firstRow.split('\n').slice(0, 4).join(' | ')}"`)

// player page via first result link
await page.locator('table.data tbody tr a').first().click()
await page.waitForSelector('.radar-wrap svg', { timeout: 10000 })
const pname = await page.locator('h1').first().innerText()
const attrsUnknown = await page.locator('.unknown-val').count()
check('player page renders radar + attrs', pname.length > 2,
  `player="${pname}" unknown-markers=${attrsUnknown} (rendered as UNKNOWN, not 0)`)
const pageText = await page.locator('body').innerText()
check('player page shows provenance', pageText.includes('CC0') && /provenance/i.test(pageText),
  'license + provenance section visible (CSS uppercases section titles)')

// ---------------------------------------------------------------- recommend
await page.goto(BASE + '/recommend', { waitUntil: 'networkidle' })
await page.locator('.chips button', { hasText: 'CM' }).first().click()
await page.locator('button.primary', { hasText: /Run recommendation/ }).click()
await page.waitForSelector('.score-hero .n', { timeout: 30000 })
const score = await page.locator('.score-hero .n').first().innerText()
const bestName = await page.locator('.score-hero').locator('xpath=../..').locator('h2 a').first().innerText()
const summary = await page.locator('.card p').first().innerText()
check('recommendation workflow renders winner+score', /^\d\.\d+$/.test(score.trim()),
  `best="${bestName}" score=${score} summary="${summary.slice(0, 70)}..."`)
// expand evidence on first ranked row
await page.locator('button', { hasText: 'Evidence' }).first().click()
await page.waitForSelector('.badge.unknown, .badge.ok', { timeout: 5000 })
const evText = await page.locator('td[colspan] .grid').first().innerText()
check('evidence panel shows components incl. honest UNKNOWNs',
  evText.includes('Team Fit') && /UNKNOWN|INSUFFICIENT/.test(evText),
  `evidence excerpt="${evText.replace(/\n/g, ' | ').slice(0, 120)}"`)

// ---------------------------------------------------------------- version switch FC27
await page.locator('.topbar .chip', { hasText: 'FC27' }).click()
await page.waitForTimeout(500)
await page.locator('button.primary', { hasText: /Run recommendation/ }).click()
await page.waitForSelector('.error-box', { timeout: 15000 })
const errText = await page.locator('.error-box').innerText()
check('FC27 recommendation shows honest NO_DATA error',
  errText.includes('NO ingested production data') && errText.includes('fabricated'),
  `error="${errText.split('\n').slice(0, 2).join(' ')}"`)
await page.goto(BASE + '/search?q=mbappe', { waitUntil: 'networkidle' })
await page.waitForTimeout(1200)
const bodyText = await page.locator('body').innerText()
check('FC27 search shows NO_DATA callout + zero results',
  bodyText.includes('NO_DATA') && bodyText.includes('No players match'),
  'callout + empty state visible, no FC26 leakage')
// switch back
await page.locator('.topbar .chip', { hasText: 'FC26' }).click()

// ---------------------------------------------------------------- compare UNKNOWN prices
await page.goto(BASE + '/search?q=silva', { waitUntil: 'networkidle' })
await page.waitForSelector('table.data tbody tr input[type=checkbox]')
await page.locator('table.data tbody tr input[type=checkbox]').nth(0).check()
await page.locator('table.data tbody tr input[type=checkbox]').nth(1).check()
await page.locator('button', { hasText: /Compare 2 selected/ }).click()
await page.waitForURL('**/compare**', { timeout: 10000 })
await page.waitForSelector('.chip.on', { timeout: 10000 })   // hydrate from ?ids=
await page.locator('button.primary', { hasText: /^Compare/ }).click()
await page.waitForSelector('table.data tbody tr', { timeout: 20000 })
const cmpText = await page.locator('body').innerText()
check('compare renders + market price row is UNKNOWN (never 0)',
  cmpText.includes('Market price') && cmpText.includes('UNKNOWN'),
  'side-by-side table with UNKNOWN prices')

// ---------------------------------------------------------------- auth flow via UI
let email = `browser-audit-${Date.now()}@example.com`
for (let attempt = 1; ; attempt++) {
  await page.goto(BASE + '/signup', { waitUntil: 'networkidle' })
  await page.locator('input[type=email]').fill(email)
  await page.locator('input[type=password]').first().fill('Browser-Passw0rd!1')
  await page.locator('input[type=password]').nth(1).fill('Browser-Passw0rd!1')
  await page.locator('button[type=submit]').click()
  const reached = await page.waitForURL('**/dashboard', { timeout: 10000 })
    .then(() => true).catch(() => false)
  if (reached) break
  const body = await page.locator('body').innerText()
  // The auth router is rate limited to 10 req/min/IP — back off, don't fail the product.
  if (attempt < 3 && /429|too many|rate/i.test(body)) {
    console.log('  [info] auth rate-limited (429); waiting 62s for the window to reset...')
    await page.waitForTimeout(62000)
    email = `browser-audit-${Date.now()}@example.com`
    continue
  }
  throw new Error('signup did not reach dashboard: ' + body.slice(0, 300))
}
await page.waitForFunction(() => document.body.innerText.includes('CAPABILITY HONESTY FLAGS'),
  { timeout: 10000 }).catch(() => {})
await page.waitForTimeout(800)   // let the reference fetch resolve
const dash = await page.locator('body').innerText()
check('signup -> dashboard via UI', dash.includes(email), `dashboard shows ${email}`)
check('dashboard shows capability honesty flags',
  dash.includes('NOT VERIFIED') && dash.includes('market data available'),
  'capability flags rendered (NOT VERIFIED where data is missing)')

// saved players via UI (star on search page)
await page.goto(BASE + '/search?q=alisson', { waitUntil: 'networkidle' })
await page.waitForSelector('table.data tbody tr button[title*="Save"]')
await page.locator('table.data tbody tr button[title*="Save"]').first().click()
await page.waitForTimeout(800)
await page.goto(BASE + '/saved', { waitUntil: 'networkidle' })
const savedText = await page.locator('body').innerText()
check('saved players flow via UI', /Alisson/i.test(savedText), 'saved list shows the player')

// squad builder via UI
await page.goto(BASE + '/squads', { waitUntil: 'networkidle' })
await page.locator('button', { hasText: '+ New squad' }).click()
await page.locator('input[placeholder="My Squad"]').fill('Browser Audit XI')
await page.locator('select').selectOption('4-3-3')
await page.locator('button', { hasText: 'Create' }).click()
await page.waitForTimeout(1500)
const squadsText = await page.locator('body').innerText()
check('squad created via UI', squadsText.includes('Browser Audit XI'), 'squad card visible')
await page.locator('a', { hasText: 'Browser Audit XI' }).first().click()
await page.waitForSelector('.pitch .slot-btn', { timeout: 10000 })
const slotCount = await page.locator('.pitch .slot-btn').count()
check('squad pitch renders 11 slots', slotCount === 11, `slots=${slotCount}`)
// assign GK via modal
await page.locator('.pitch .slot-btn').first().click()
await page.waitForSelector('.modal input[placeholder*="Search"]')
await page.locator('.modal input[placeholder*="Search"]').fill('alisson')
await page.waitForTimeout(1200)
await page.locator('.modal button', { hasText: 'Alisson' }).first().click()
await page.waitForTimeout(1200)
const pitchText = await page.locator('.pitch').innerText()
check('slot assignment via UI renders on pitch', pitchText.includes('Alisson'),
  'GK slot now shows Alisson')
const evalText = await page.locator('body').innerText()
check('evaluation shows INSUFFICIENT_EVIDENCE chemistry',
  evalText.includes('INSUFFICIENT EVIDENCE'), 'honest chemistry status rendered')

// ---------------------------------------------------------------- 404 + profile
await page.goto(BASE + '/definitely-not-a-route', { waitUntil: 'networkidle' })
const nf = await page.locator('body').innerText()
check('unknown route renders 404 page', nf.includes('404') && nf.includes('Page not found'),
  'client-side 404, nothing fabricated')
// The profile fetches /api/auth/me, which counts toward the 10 req/min auth
// rate limit — if a previous audit run exhausted the window, back off once.
let prof = ''
for (let attempt = 1; attempt <= 2; attempt++) {
  await page.goto(BASE + '/profile', { waitUntil: 'networkidle' })
  await page.waitForTimeout(600)
  prof = await page.locator('body').innerText()
  if (prof.includes(email)) break
  // No visible 429 text: when the boot /me is rate-limited the session simply
  // renders logged-out. In DEV, StrictMode double-fires the boot effect, so a
  // full audit consumes ~15 auth calls against the 10/min window — back off.
  if (attempt === 1) {
    console.log('  [info] profile did not render user (likely /me 429 in dev StrictMode); waiting 62s...')
    await page.waitForTimeout(62000)
  }
}
check('profile page renders account + session info',
  prof.includes(email) && prof.includes('Log out everywhere'), 'profile content visible')

// ---------------------------------------------------------------- console hygiene
check('no uncaught JS exceptions', pageErrors.length === 0,
  pageErrors.length ? pageErrors.slice(0, 3).join(' || ') : 'zero pageerrors across all flows')
check('no unexpected console errors', consoleErrors.length === 0,
  consoleErrors.length ? consoleErrors.slice(0, 3).join(' || ') : 'zero (expected 4xx resource logs filtered)')

await browser.close()
const fails = results.filter((r) => !r.ok)
console.log(`\nBROWSER TOTAL: ${results.length} checks | PASS ${results.length - fails.length} | FAIL ${fails.length}`)
process.exit(fails.length ? 1 : 0)
