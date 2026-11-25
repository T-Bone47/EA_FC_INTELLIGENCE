import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { chromium } from 'playwright'

const base = new URL(process.env.E2E_API_URL)
assert.equal(base.hostname, '127.0.0.1', 'Use the disposable loopback API')
const output = process.env.STADIUM_RESULTS_DIR
assert.ok(output, 'Set STADIUM_RESULTS_DIR')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
  args: ['--disable-background-networking', '--disable-component-update', '--disable-sync',
    '--disable-breakpad', '--disable-crash-reporter', '--no-pings', '--proxy-server=http://127.0.0.1:9',
    '--proxy-bypass-list=127.0.0.1', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'],
})
const page = await browser.newPage({ baseURL: base.origin, viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' })
await page.context().route('**/*', route => new URL(route.request().url()).origin === base.origin
  ? route.continue() : route.abort('blockedbyclient'))
page.setDefaultTimeout(20000)
const axe = process.env.AXE_PATH ? await readFile(process.env.AXE_PATH, 'utf8') : null
const results = { status: 'running', checks: [], pages: [], responsive: [], accessibility: [], pageErrors: [] }
page.on('pageerror', err => results.pageErrors.push(err.message))
const heading = name => page.getByRole('heading', { level: 1, name })
const scan = async name => {
  if (!axe) return
  await page.evaluate(axe)
  const findings = await page.evaluate(async () => {
    const scan = await window.axe.run({ runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } })
    return { passes: scan.passes.length, violations: scan.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })) }
  })
  results.accessibility.push({ view: name, ...findings })
}
const capture = async name => {
  await page.screenshot({ path: join(output, name + '.png'), fullPage: true, animations: 'disabled', timeout: 15000 })
  results.pages.push(name)
}
const bounds = async () => page.evaluate(() => ({
  viewport: innerWidth, page: document.documentElement.scrollWidth,
  main: document.querySelector('main').scrollWidth,
  mainWidth: document.querySelector('main').clientWidth,
}))
async function checkWidths(view) {
  const original = page.viewportSize()
  for (const width of [1600, 1440, 1280, 1024, 768, 390, 360]) {
    await page.setViewportSize({ width, height: 900 })
    const measured = await bounds()
    results.responsive.push({ view, ...measured })
    assert.ok(measured.page <= width, JSON.stringify({ view, ...measured }))
  }
  await page.setViewportSize(original)
}
async function visit(path, name) {
  await page.goto(path)
  await heading(name).waitFor()
}

try {
  const startup = performance.now()
  await visit('/', 'Build a smarter squad. Play your football.')
  await page.getByRole('link', { name: 'Find my best fit' }).waitFor()
  results.overview_ready_ms = Math.round(performance.now() - startup)
  await capture('overview')
  await checkWidths('overview')
  await scan('overview')
  await page.keyboard.press('Tab')
  await page.getByRole('link', { name: 'Skip to content' }).focus()
  await page.keyboard.press('Enter')
  assert.equal(await page.evaluate(() => document.activeElement.id), 'main')

  await page.getByRole('button', { name: 'FC27', exact: true }).click()
  await page.getByRole('link', { name: 'Discover', exact: true }).click()
  await page.getByLabel('Include FC27 research players').check()
  await page.getByLabel('Search players', { exact: true }).fill('Haaland')
  await page.locator('.discovery-tile').filter({ hasText: 'Haaland' }).first().waitFor()
  await capture('discover')
  await checkWidths('discover')
  await page.getByRole('button', { name: 'Table', exact: true }).click()
  await page.getByRole('table').getByRole('link', { name: /Haaland/ }).first().click()
  await page.getByRole('heading', { name: /Haaland/ }).first().waitFor()
  assert.match(page.url(), /game_version=FC27.*include_research_data=true/)
  results.checks.push('Keyboard skip link, sidebar, FC27 opt-in search, grid/table switch and player details')

  await page.getByRole('link', { name: 'Intelligence', exact: true }).click()
  await page.getByLabel("Men's Football", { exact: true }).check()
  await page.getByLabel('Formation', { exact: true }).selectOption('4-3-3')
  await page.getByLabel('Formation slot', { exact: true }).selectOption('ST')
  await page.getByLabel('Tactical style', { exact: true }).selectOption('HIGH_PRESS')
  const start = performance.now()
  await page.getByRole('button', { name: 'Find players' }).click()
  await page.getByTestId('ix-card').first().waitFor()
  results.recommendation_submit_to_visible_ms = Math.round(performance.now() - start)
  const context = await page.getByTestId('submitted-request').textContent()
  assert.match(context, /FC27.*ST.*high press/)
  await page.getByRole('button', { name: /^Inspect / }).nth(1).click()
  await page.getByRole('complementary', { name: 'Recommendation explanation' }).getByText('Key factors').waitFor()
  await page.getByRole('checkbox', { name: /^Compare / }).nth(0).check()
  await page.getByRole('checkbox', { name: /^Compare / }).nth(1).check()
  await page.getByRole('button', { name: 'Compare 2 players' }).click()
  await page.locator('.ix-cmp').waitFor()
  await capture('intelligence')
  await checkWidths('intelligence')
  await scan('intelligence')
  results.checks.push('FC27 V3.2 formation-slot ranking, explanation inspector and bound-context player comparison')

  await visit('/compare?scope=cards', 'Compare card versions')
  await page.getByLabel('Use local FC27 card research').check()
  await page.getByLabel('Find a card by name or item ID').fill('Yamal')
  for (const source of ['67386507', '84163723']) await page.getByRole('checkbox', { name: new RegExp(source + '$') }).check()
  await page.getByRole('button', { name: 'Compare selected versions' }).click()
  await page.getByText(/Why the higher item leads/).waitFor()
  await capture('comparison')
  await checkWidths('comparison')
  await scan('comparison')
  results.checks.push('Dedicated card comparison route and exact special-item IDs')

  await visit('/cards/squad-lab', 'Ultimate Team Squad Lab')
  await page.getByLabel('Use local FC27 card research').check()
  await page.getByLabel('Search card items').fill('Yamal')
  for (const source of ['67386507', '84163723', '277643']) await page.getByRole('button', { name: new RegExp('Add .*' + source + '$') }).click()
  await page.getByRole('button', { name: /^RW\s*Unfilled$/ }).focus()
  await page.keyboard.press('Enter')
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), 'Assign RW')
  const rw = page.getByLabel('Assign RW', { exact: true })
  const weak = await rw.locator('option').filter({ hasText: '277643' }).getAttribute('value')
  await rw.selectOption(weak)
  await page.getByLabel('Replacement mode').selectOption('one')
  await page.getByRole('button', { name: 'Preview card squad' }).click()
  await page.getByRole('heading', { name: 'Squad DNA', exact: true }).waitFor()
  await capture('squad-lab')
  await page.locator('#squad-dna').screenshot({ path: join(output, 'squad-dna.png'), animations: 'disabled' })
  results.pages.push('squad-dna')
  await page.locator('#upgrade-studio').screenshot({ path: join(output, 'upgrades.png'), animations: 'disabled' })
  results.pages.push('upgrades')
  await checkWidths('squad-lab')
  await page.setViewportSize({ width: 360, height: 900 })
  await page.getByRole('button', { name: 'Apply replacements' }).click()
  assert.notEqual(await rw.inputValue(), weak)
  await page.getByRole('button', { name: 'Undo last edit' }).click()
  assert.equal(await rw.inputValue(), weak)
  await scan('squad-lab-360')
  await capture('squad-lab-mobile')
  await page.getByRole('button', { name: 'Menu', exact: true }).click()
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Overview' }).waitFor()
  assert.equal(await page.evaluate(() => document.activeElement.textContent.trim()), '⌂Overview')
  await page.keyboard.press('Escape')
  assert.equal(await page.getByRole('button', { name: 'Menu', exact: true }).getAttribute('aria-expanded'), 'false')
  results.checks.push('Keyboard pitch assignment, seven-width layout, backend upgrade, apply/undo and mobile menu')

  await visit('/cards/performance', 'Performance Evidence Lab')
  await page.getByLabel('Enable local FC27 performance research').check()
  await page.getByLabel('Research card', { exact: true }).waitFor()
  await page.setViewportSize({ width: 1440, height: 1000 })
  await capture('evidence')
  await checkWidths('evidence')
  await scan('evidence')
  results.checks.push('Live Phase 31 evidence cohort')

  await visit('/profile#account-settings', 'Log in')
  await page.getByRole('button', { name: 'Forgot password?' }).click()
  await page.getByText(/Password reset is unavailable/).waitFor()
  await capture('login')
  await checkWidths('login')
  await scan('login')
  await page.getByRole('navigation', { name: 'Account actions' }).getByRole('link', { name: 'Create account' }).click()
  const suffix = randomUUID()
  const email = 'phase32-' + suffix + '@example.com'
  const password = 'Test-' + suffix
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel(/Display name/).fill('Migration check')
  await page.getByLabel('Password', { exact: false }).first().fill(password)
  await page.getByLabel('Confirm password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign up', exact: true }).click()
  await heading('Profile').waitFor()
  assert.match(page.url(), /\/profile#account-settings$/)
  await capture('profile')
  await checkWidths('profile')
  await scan('profile')
  await page.getByRole('button', { name: 'Log out', exact: true }).click()
  await visit('/login', 'Log in')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await heading('Build a smarter squad. Play your football.').waitFor()
  results.checks.push('Signup with return-to hash, authenticated profile, logout, login and recovery availability')

  const filtered = await page.request.get('/api/research/fc27/cards?include_research_data=true&q=Yamal&position=RW&ovr_min=80')
  assert.equal(filtered.status(), 200)
  const rankedItems = (await filtered.json()).items
  assert.ok(rankedItems.length >= 2)
  assert.ok(rankedItems.every(item => item.positions.includes('RW') && item.overall >= 80))
  const exact = await page.request.get('/api/research/fc27/cards/items/' + rankedItems[0].entity_id + '?include_research_data=true')
  assert.equal(exact.status(), 200)
  const item = await exact.json()
  assert.equal(item.source_item_id, rankedItems[0].source_item_id)
  assert.ok(Object.keys(item.attributes).length > 0)
  const denied = await page.request.get('/api/research/fc27/cards/items/00000000-0000-0000-0000-000000000000')
  assert.equal(denied.status(), 422)
  const unavailable = await page.request.get('/api/research/fc27/cards/items/00000000-0000-0000-0000-000000000000?include_research_data=true')
  assert.equal(unavailable.status(), 404)
  const outside = await page.request.get('/api/research/fc27/cards?include_research_data=true', { headers: { Forwarded: 'for=127.0.0.1' } })
  assert.equal(outside.status(), 403)
  results.checks.push('Server-side item filters, exact detail, opt-in, release membership and forwarded-request refusals')
  assert.deepEqual(results.pageErrors, [])
  assert.deepEqual(results.accessibility.filter(x => x.violations.length), [])
  results.status = 'passed'
} catch (error) {
  results.status = 'failed'
  try { await capture('failed-view') } catch { /* Keep the underlying journey failure. */ }
  results.error = String(error)
  throw error
} finally {
  await writeFile(join(output, 'BROWSER_E2E_RESULTS.json'), JSON.stringify(results, null, 2) + '\n')
  await browser.close()
}
