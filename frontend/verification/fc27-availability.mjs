import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { chromium } from 'playwright'

const local = new URL(process.env.E2E_API_URL)
const production = new URL(process.env.E2E_PRODUCTION_URL)
assert.equal(local.hostname, '127.0.0.1')
assert.equal(production.hostname, '127.0.0.1')
const output = process.env.AVAILABILITY_RESULTS_DIR
assert.ok(output)
await mkdir(output, { recursive: true })

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
  args: ['--disable-background-networking', '--disable-component-update', '--disable-sync',
    '--disable-breakpad', '--disable-crash-reporter', '--no-pings', '--proxy-server=http://127.0.0.1:9',
    '--proxy-bypass-list=127.0.0.1', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'],
})
const checks = []
const errors = []
const report = { status: 'failed', checks, errors }
async function open(baseURL) {
  const page = await browser.newPage({ baseURL: baseURL.origin,
    viewport: { width: 1280, height: 950 }, serviceWorkers: 'block' })
  page.setDefaultTimeout(25000)
  await page.context().route('**/*', route => new URL(route.request().url()).origin === baseURL.origin
    ? route.continue() : route.abort('blockedbyclient'))
  page.on('pageerror', error => errors.push(error.message))
  return page
}

try {
  const page = await open(local)
  const localResponse = await page.request.get('/api/meta/availability')
  assert.equal(localResponse.status(), 200)
  const localStatus = await localResponse.json()
  const fc27 = localStatus.versions.FC27
  for (const scope of Object.values(fc27)) {
    assert.equal(scope.research.status, 'RESEARCH_RELEASE_AVAILABLE')
    assert.ok(scope.research.record_count > 0 && scope.research.reference_ready)
  }
  report.local_availability = localStatus
  const forwarded = await page.request.get('/api/meta/availability', { headers: { Forwarded: 'for=127.0.0.1' } })
  assert.equal((await forwarded.json()).versions.FC27.ut_card.research.status, 'RESEARCH_ACCESS_DISABLED')
  const header = page.getByRole('status', { name: 'FC27 data availability' })
  const toggle = page.getByRole('checkbox', { name: 'Enable FC27 local research' })
  await page.goto('/search')
  await page.getByRole('button', { name: 'FC27', exact: true }).click()
  await header.getByText('Players · Local Research Available').waitFor()
  await header.getByText('Cards · Local Research Available').waitFor()
  await header.getByText('Production Data Unavailable').waitFor()
  assert.ok(!(await page.locator('body').innerText()).includes('NO_DATA'))
  assert.equal(await toggle.isChecked(), false)
  await toggle.check()
  await header.getByText('Players · Local Research Active').waitFor()
  await header.getByText('Cards · Local Research Active').waitFor()
  await page.getByRole('group', { name: 'Position filter' }).getByRole('button', { name: 'ST', exact: true }).click()
  const query = page.waitForResponse(r => r.url().includes('/api/players?') && new URL(r.url()).searchParams.get('q') === 'Haaland')
  await page.getByRole('textbox', { name: 'Search players', exact: true }).fill('Haaland')
  const filtered = await query
  assert.equal(filtered.status(), 200)
  const search = new URL(filtered.url()).searchParams
  assert.equal(search.get('game_version'), 'FC27')
  assert.equal(search.get('include_research_data'), 'true')
  assert.equal(search.get('position'), 'ST')
  await page.getByRole('link', { name: 'Erling Haaland', exact: true }).click()
  await page.getByRole('heading', { name: 'Erling Haaland', exact: true }).waitFor()
  await page.getByText('FC27 research snapshot', { exact: true }).waitFor()
  checks.push('Shared opt-in, scoped FC27 player filters, search and player details')

  await page.goto('/recommend?position=ST')
  await page.waitForURL('**/intelligence?position=ST')
  await header.getByText('Players · Local Research Active').waitFor()
  assert.equal(await page.getByLabel('Position', { exact: true }).inputValue(), 'ST')
  await page.getByLabel('Formation', { exact: true }).selectOption('4-3-3')
  await page.getByLabel('Formation slot', { exact: true }).selectOption('ST')
  await page.getByLabel("Men's Football", { exact: true }).check()
  await page.getByLabel('Tactical style', { exact: true }).selectOption('HIGH_PRESS')
  await page.getByLabel('Preferred attribute', { exact: true }).selectOption('stamina')
  await page.getByLabel('Preferred PlayStyle+', { exact: true }).fill('Quick Step')
  const [ranked] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/v3/recommendations') && r.request().method() === 'POST'),
    page.getByRole('button', { name: 'Find players' }).click(),
  ])
  assert.equal(ranked.status(), 200, await ranked.text())
  const req = ranked.request().postDataJSON()
  assert.deepEqual(req, { game_version: 'FC27', position: 'ST', tactical_profile: 'HIGH_PRESS', limit: 10,
    include_research_data: true, division: "Men's Football", formation: '4-3-3', slot: 'ST',
    attribute_preferences: [{ attribute: 'stamina', weight: 2 }], desired_playstyles_plus: ['Quick Step'] })
  const results = await ranked.json()
  assert.ok(results.ranked.length >= 2)
  assert.ok(results.leading_pair?.status)
  assert.ok(Math.abs(results.leading_pair.margin_low - (results.ranked[0].score - results.ranked[1].score_upper_bound)) < 1e-9)
  assert.ok(JSON.stringify(results.dataset).includes(fc27.game_player.research.release_id))
  assert.equal(results.dataset.research_only, true)
  await page.getByTestId('ix-card').first().waitFor()
  await page.getByText(/Modelled fit margin/).first().waitFor()
  const options = page.getByRole('checkbox', { name: /^Compare / })
  await options.nth(0).check()
  await options.nth(1).check()
  const cmp = page.waitForResponse(r => r.url().endsWith('/api/v3/compare') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Compare 2 players' }).click()
  const playerComparison = await cmp
  assert.equal(playerComparison.status(), 200)
  const comparedPlayers = await playerComparison.json()
  assert.equal(comparedPlayers.players.length, 2)
  assert.ok(comparedPlayers.pairwise[0].decision_evidence.status)
  await page.locator('.ix-cmp').waitFor()
  await page.screenshot({ path: join(output, 'FC27_STUDIO.png') })
  report.player_recommendation = { engine_version: results.engine_version, dataset: results.dataset,
    request: req, ranked: results.ranked.length, leading_pair: results.leading_pair,
    pairwise_decision_evidence: comparedPlayers.pairwise[0].decision_evidence }
  checks.push('Legacy URL redirects to V3.2, honors context and preferences, and compares two real FC27 players')

  await page.getByRole('link', { name: 'Discover', exact: true }).click()
  await page.getByRole('link', { name: 'Card versions', exact: true }).click()
  await page.getByLabel('Find a card by name or item ID').fill('Yamal')
  for (const id of ['67386507', '84163723']) await page.getByRole('checkbox', { name: new RegExp(id + '$') }).check()
  const compareCards = page.waitForResponse(r => r.url().endsWith('/api/research/fc27/cards/compare'))
  await page.getByRole('button', { name: 'Compare selected versions' }).click()
  const exact = await compareCards
  assert.equal(exact.status(), 200)
  const cardCompare = await exact.json()
  assert.ok(JSON.stringify(cardCompare.dataset).includes(fc27.ut_card.research.release_id))
  assert.equal(cardCompare.dataset.research_only, true)
  assert.ok(cardCompare.pairwise[0].decision_evidence.status)
  assert.notEqual(...exact.request().postDataJSON().card_ids)
  await page.getByText(/Why the higher item leads/).waitFor()
  report.card_comparison = { dataset: cardCompare.dataset, item_ids: exact.request().postDataJSON().card_ids,
    pairwise_decision_evidence: cardCompare.pairwise[0].decision_evidence }
  checks.push('Opt-in carried to Discover Cards, with distinct item IDs and the card-specific reference')

  await page.getByRole('link', { name: 'Squad Lab', exact: true }).click()
  await page.getByLabel('Search card items').fill('Yamal')
  for (const id of ['67386507', '84163723', '277643']) await page.getByRole('button', { name: new RegExp('Add .*' + id + '$') }).click()
  await page.getByLabel('Search card items').fill('Courtois')
  await page.getByRole('button', { name: /Add .*Courtois/i }).first().click()
  await page.getByLabel('Assign GK', { exact: true }).selectOption({ index: 1 })
  await page.getByLabel('Lock GK', { exact: true }).check()
  const preview = page.waitForResponse(r => r.url().endsWith('/api/research/fc27/cards/squad/preview'))
  await page.getByRole('button', { name: 'Preview card squad' }).click()
  const optimized = await preview
  assert.equal(optimized.status(), 200)
  const squad = await optimized.json()
  const goalkeeper = squad.optimized.slots.find(s => s.slot === 'GK')
  assert.equal(goalkeeper.score, null)
  assert.ok(goalkeeper.item && squad.optimized.scored > 0)
  await page.getByRole('heading', { name: 'Squad DNA', exact: true }).waitFor()
  await page.getByText(/no validated goalkeeper scoring reference/).waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await page.screenshot({ path: join(output, 'FC27_SQUAD_MOBILE.png') })
  report.squad = { scored: squad.optimized.scored, goalkeeper_score: goalkeeper.score, status: squad.solver_status }
  await toggle.uncheck()
  await header.getByText('Cards · Local Research Available').waitFor()
  assert.equal(await page.getByLabel('Search card items').count(), 0)
  await page.goto('/intelligence')
  assert.equal(await toggle.isChecked(), false)
  assert.equal(await page.getByRole('button', { name: 'Find players' }).isDisabled(), true)
  assert.equal(await page.getByTestId('ix-card').count(), 0)
  await page.goto('/search')
  await header.getByText('Players · Local Research Available').waitFor()
  assert.equal(await page.getByRole('textbox', { name: 'Search players', exact: true }).count(), 0)
  await page.screenshot({ path: join(output, 'FC27_OPT_IN_REQUIRED.png') })
  checks.push('Real squad optimization, unscored locked goalkeeper, mobile layout and revocation across workspaces')

  const publicPage = await open(production)
  await publicPage.goto('/search')
  await publicPage.getByRole('button', { name: 'FC27', exact: true }).click()
  await publicPage.getByRole('status', { name: 'FC27 data availability' }).getByText('Players · Research Access Disabled').waitFor()
  assert.equal(await publicPage.getByRole('checkbox', { name: 'Enable FC27 local research' }).count(), 0)
  const publicStatus = (await (await publicPage.request.get('/api/meta/availability')).json())
  assert.equal(publicStatus.environment, 'production')
  for (const scope of Object.values(publicStatus.versions.FC27)) {
    assert.equal(scope.local, null)
    assert.equal(scope.research.record_count, null)
    assert.equal(scope.production.status, 'PRODUCTION_NOT_APPROVED')
  }
  for (const endpoint of ['/api/players?game_version=FC27&include_research_data=true', '/api/meta/reference?game_version=FC27&include_research_data=true',
    '/api/research/fc27/cards?include_research_data=true']) assert.equal((await publicPage.request.get(endpoint)).status(), 403)
  assert.equal((await publicPage.request.post('/api/v3/recommendations', { data: req })).status(), 403)
  assert.equal((await publicPage.request.post('/api/research/fc27/cards/squad/preview',
    { data: optimized.request().postDataJSON() })).status(), 403)
  await publicPage.screenshot({ path: join(output, 'FC27_PRODUCTION_RESTRICTED.png') })
  report.production_availability = publicStatus
  checks.push('Production app independently refuses player, reference, recommendation, card and squad research requests')
  assert.deepEqual(errors, [])
  report.status = 'passed'
} catch (error) {
  report.error = String(error)
  throw error
} finally {
  await writeFile(join(output, 'FC27_AVAILABILITY_BROWSER.json'), JSON.stringify(report, null, 2) + '\n')
  await browser.close()
}
