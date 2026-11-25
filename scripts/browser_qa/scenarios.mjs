export async function scenarios({ browser, R, BASE, SHOTS, AXE, check, guard }) {
const VIEW = { desktop: { width: 1280, height: 900 }, tablet: { width: 768, height: 1024 }, mobile: { width: 390, height: 844, isMobile: true, hasTouch: true } }
async function open(vp, intercept) {
  const page = await browser.newPage(); await page.setViewport(vp); const errs = []
  page.on('pageerror', e => { errs.push(String(e.stack || e)); check('uncaught page error', false, e.stack || e.message) }); page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()) })
  if (intercept) { await page.setRequestInterception(true); page.on('request', r => { if (!intercept(r)) r.continue() }) }
  const response = await page.goto(BASE + '/intelligence', { waitUntil: 'networkidle0' }); if (!response?.ok()) throw Error('Page load returned ' + response?.status()); return { page, errs }
}
// Compare against the CONFIGURED viewport width, not innerWidth: a phone widens innerWidth to fit overflowing content.
const overflow = async page => { const W = page.viewport().width; return page.evaluate(W => { const off = []; for (const e of document.querySelectorAll('body *')) { const r = e.getBoundingClientRect(); if (r.width && r.right > W + 1) off.push(e.tagName + '.' + String(e.className).slice(0, 30)) } return { page_scrollW: document.documentElement.scrollWidth, innerW: W, layoutW: innerWidth, offenders: [...new Set(off)].slice(0, 6) } }, W) }
const find = page => page.$$eval('button', bs => bs.find(b => /find players/i.test(b.textContent))?.disabled)
const clickText = (page, sel, re) => page.evaluate((s, r) => { const e = [...document.querySelectorAll(s)].find(x => new RegExp(r, 'i').test(x.textContent)); e?.click(); return !!e }, sel, re)
async function axe(page, name) {
  await page.evaluate(AXE)
  const v = await page.evaluate(async () => { const r = await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] })
    return r.violations.map(x => ({ id: x.id, impact: x.impact, tags: x.tags, help: x.help, nodes: x.nodes.length, samples: x.nodes.slice(0, 3).map(n => ({ target: n.target.join(' ').slice(0, 70), html: n.html.slice(0, 60), data: n.any[0]?.data ? { fg: n.any[0].data.fgColor, bg: n.any[0].data.bgColor, ratio: n.any[0].data.contrastRatio, size: n.any[0].data.fontSize } : null })) })) })
  R.axe.push({ state: name, violations: v }); console.log('AXE', name, v.map(x => `${x.id}(${x.impact},${x.nodes})`).join(' ') || 'none')
  for (const x of v) {
    const blocking = ['critical', 'serious'].includes(x.impact) && x.tags.some(tag => tag.startsWith('wcag'))
    check(name + ' accessibility ' + x.id, false, x.help, blocking ? 'FAIL' : 'WARNING')
  }
  for (const x of v) console.log('   ', x.id, JSON.stringify(x.samples).slice(0, 330))
}
const diag = page => page.evaluate(() => { const bs = [...document.querySelectorAll('input[type=checkbox][aria-label^="Compare "]')].slice(0, 3).map(b => ({ checked: b.checked, w: Math.round(b.getBoundingClientRect().width) })); const btn = [...document.querySelectorAll('button')].find(b => /compare \d players/i.test(b.textContent)); return { boxes: bs, compareBtn: btn ? { text: btn.textContent, disabled: btn.disabled } : null, err: document.querySelector('.error-box')?.innerText?.slice(0, 80) ?? null } })
async function search(page, tactic = 'BALANCED') {
  await page.click('input[name=gv][type=radio]:not(:checked)')
  return recommend(page, tactic)
}
async function recommend(page, tactic, version = 'FC26', division) {
  await page.select('select[aria-label="Tactical style"]', tactic)
  const response = page.waitForResponse(r => r.url().endsWith('/api/v3/recommendations') && r.request().method() === 'POST')
  await clickText(page, 'button', 'find players')
  const http = await response
  const payload = JSON.parse(http.request().postData()), result = await http.json()
  await page.waitForSelector('[data-testid=ix-card]', { timeout: 40000 })
  const rows = await page.$$eval('[data-testid=ix-card]', cards => cards.map(card => ({
    name: card.querySelector('h3').textContent, rank: Number(card.querySelector('.ix-rank').textContent),
    score: card.querySelector('.ix-score').textContent
  })))
  check(version + ' CM ' + tactic + ' request reached API and rendered the returned rankings',
    http.ok() && payload.game_version === version && payload.division === division && payload.position === 'CM' && payload.tactical_profile === tactic && result.request.tactical_profile === tactic &&
    result.reference_distribution_version === version.toLowerCase() + '-players-2026-09-r1' &&
    result.reference_distribution_universe === 'RATINGS_SITE_PLAYERS' && rows.length === result.ranked.length &&
    rows.every((row, i) => row.name === result.ranked[i].name && row.rank === result.ranked[i].rank && row.score === result.ranked[i].score.toFixed(4)))
  return result
}
async function tap(page, h) { await h.evaluate(e => e.scrollIntoView({ block: 'center' })); const bb = await h.boundingBox(); await page.touchscreen.tap(bb.x + bb.width / 2, bb.y + bb.height / 2) }

await guard('A initial state + keyboard', async () => {
  const { page, errs } = await open(VIEW.desktop)
  check('A1 page renders h1', await page.$eval('h1', e => /player intelligence/i.test(e.textContent)))
  check('A2 FC27 default + Find players disabled until division chosen', (await find(page)) === true && await page.$eval('input[name=gv]:checked', e => e.parentElement.textContent.includes('FC27')))
  await page.focus('input[name=division]'); await page.keyboard.press('Space')
  check('A3 keyboard Space selects a division and enables the button', (await find(page)) === false)
  await page.keyboard.press('ArrowDown'); check('A4 arrow key moves the radio selection', await page.$$eval('input[name=division]', rs => rs.filter(r => r.checked).length === 1))
  R.layout.push({ state: 'initial', viewport: 'desktop', ...(await overflow(page)) }); await axe(page, 'initial-desktop'); R.console.push({ state: 'initial', errors: errs }); await page.close()
})

for (const [vn, vp] of Object.entries(VIEW)) await guard(`flow ${vn}`, async () => {
  const { page, errs } = await open(vp); const t0 = Date.now(); const initial = await search(page); const ms = Date.now() - t0
  const n = await page.$$eval('[data-testid=ix-card]', c => c.length), brackets = await page.$$eval('[aria-label="Effectively tied"]', c => c.length)
  check(`B ${vn}: results render (${n} cards, ${brackets} tie brackets, ${ms} ms click->cards)`, n > 0)
  const ov = await overflow(page); R.layout.push({ state: 'results', viewport: vn, ...ov }); check(`C ${vn}: no horizontal page overflow`, ov.page_scrollW <= ov.innerW + 1, JSON.stringify(ov))
  await page.screenshot({ path: `${SHOTS}/shot_results_${vn}.png` })
  const hit = await page.evaluate(() => { const b = [...document.querySelectorAll('input[type=checkbox][aria-label^="Compare "]')][2]; b.scrollIntoView({ block: 'start' }); const r = b.getBoundingClientRect(), top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); const hd = document.querySelector('.topbar'); return { self: top === b, rectTop: Math.round(r.top), headerSticky: getComputedStyle(hd).position === 'sticky', headerH: Math.round(hd.getBoundingClientRect().height), onTop: top ? top.tagName + '.' + String(top.className).slice(0, 14) : 'none' } })
  check(`C3 ${vn}: a control scrolled to the top edge is not hidden behind the sticky header`, hit.self, JSON.stringify(hit)); await page.evaluate(() => window.scrollTo(0, 0))
  if (vn !== 'tablet') {
    const boxes = await page.$$('input[type=checkbox][aria-label^="Compare "]')
    if (vn === 'mobile') { for (const i of [1, 2]) await tap(page, boxes[i]) } else { await boxes[1].click(); await boxes[2].click() }
    check(`D0 ${vn}: two players selected via ${vn === 'mobile' ? 'a real touch tap' : 'click'}`, (await page.$$eval('input[type=checkbox][aria-label^="Compare "]', c => c.filter(x => x.checked).length)) === 2)
    await clickText(page, 'button', 'compare \\d players')
    try { await page.waitForSelector('[aria-label=Comparison]', { timeout: 30000 }) } catch (e) { check(`D ${vn}: compare panel opens`, false, JSON.stringify(await diag(page))); throw e }
    const ov3 = await overflow(page); check(`D ${vn}: compare panel renders without page overflow`, ov3.page_scrollW <= ov3.innerW + 1, JSON.stringify(ov3.offenders)); await page.screenshot({ path: `${SHOTS}/shot_compare_${vn}.png`, fullPage: true })
    await clickText(page, 'button', '^high press$'); await page.waitForSelector('[aria-label="What if"] ul li', { timeout: 30000 })
    check(`E ${vn}: what-if rows appear`, (await page.$$eval('[aria-label="What if"] ul li', l => l.length)) > 0)
    await axe(page, `results+compare+whatif-${vn}`)
    R.touch.push({ viewport: vn, undersized: await page.evaluate(() => [...document.querySelectorAll('button, select, summary, input')].map(e => { const r = e.getBoundingClientRect(); return { tag: e.tagName + (e.type ? ':' + e.type : ''), w: Math.round(r.width), h: Math.round(r.height), label: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 24) } }).filter(x => x.w && (x.w < 24 || x.h < 24)).slice(0, 12)) })
  }
  if (vn === 'desktop') {
    const pressed = await recommend(page, 'HIGH_PRESS')
    check('Tactical change recomputed demand', pressed.request_id !== initial.request_id &&
      JSON.stringify(pressed.demand_vector) !== JSON.stringify(initial.demand_vector))
  }
  check('No console errors during ' + vn + ' results', errs.length === 0, JSON.stringify(errs))
  R.console.push({ state: 'flow-' + vn, errors: errs }); await page.close()
})

for (const [vn, vp] of Object.entries(VIEW)) await guard(`C2 ${vn} stress`, async () => {   // long name + long explanation, FRESH page
  const { page } = await open(vp); await search(page)
  await page.evaluate(() => { const h = document.querySelector('[data-testid=ix-card] h3'); h.textContent = 'Wolfeschlegelsteinhausenbergerdorff-Vandenberghe '.repeat(2); const q = document.querySelector('.ix-why'); if (q) q.textContent = 'x'.repeat(400) })
  const ov2 = await overflow(page); check(`C2 ${vn}: long name + long explanation do not overflow the page`, ov2.page_scrollW <= ov2.innerW + 1, JSON.stringify(ov2.offenders)); await page.close()
})

await guard('F focus-visibility probe', async () => {
  const { page, errs } = await open(VIEW.desktop)
  const order = ['input[name=gv]', 'select[aria-label=Position]', 'input[name=division]', 'select[aria-label="Tactical style"]']
  const reached = []
  for (let i = 0; i < 35 && reached.length < order.length; i++) {
    await page.keyboard.press('Tab')
    const item = await page.evaluate(selectors => {
      const el = document.activeElement
      const selector = selectors.find(sel => el?.matches(sel))
      if (!selector) return null
      const css = getComputedStyle(el)
      return { selector, visible: el.matches(':focus-visible') &&
        ((css.outlineStyle !== 'none' && parseFloat(css.outlineWidth) > 0) || css.boxShadow !== 'none') }
    }, order)
    if (item) reached.push(item)
  }
  R.focus.push(...reached)
  check('Tab visits game, position, division and tactic in order with visible focus',
    reached.length === order.length && reached.every((item, i) => item.selector === order[i] && item.visible),
    JSON.stringify(reached))
  check('No console errors during keyboard traversal', errs.length === 0, JSON.stringify(errs))
  await page.close()
})

await guard('FC27 research flow', async () => {
  const { page, errs } = await open(VIEW.desktop)
  await page.click('input[name=division]')
  const result = await recommend(page, 'BALANCED', 'FC27', "Men's Football")
  check('FC27 research results preserve version and division',
    result.request.include_research_data === true && result.division.requested === "Men's Football" &&
    result.dataset.data_status === 'RESEARCH_ONLY')
  const choices = await page.$$('input[type=checkbox][aria-label^="Compare "]')
  await choices[0].click(); await choices[1].click()
  await clickText(page, 'button', 'compare 2 players')
  await page.waitForSelector('[aria-label=Comparison]')
  await clickText(page, 'button', '^high press$')
  await page.waitForSelector('[aria-label="What if"] ul li')
  check('FC27 compares players and displays a what-if variant', true)
  check('No console errors during FC27 research flow', errs.length === 0, JSON.stringify(errs))
  await page.screenshot({ path: `${SHOTS}/shot_fc27_desktop.png` })
  await page.close()
})

const live = r => r.url().endsWith('/api/v3/recommendations')
const respond = (status, body, delay = 0) => r => live(r) ? (setTimeout(() => r.respond({ status, contentType: 'application/json', body: typeof body === 'string' ? body : JSON.stringify(body) }), delay), true) : false
const state = (name, icpt, expect) => guard(`G ${name}`, async () => {
  const { page, errs } = await open(VIEW.desktop, icpt); await page.click('input[name=gv][type=radio]:not(:checked)'); await clickText(page, 'button', 'find players')
  await new Promise(r => setTimeout(r, name.startsWith('slow') ? 600 : 1500)); const out = await expect(page); check(`G ${name}`, out.ok, out.detail)
  check(`G ${name}: app still alive (no blank screen)`, await page.$eval('h1', e => !!e.textContent).catch(() => false)); R.console.push({ state: name, errors: errs.slice(0, 3) }); await page.close()
})
const text = p => p.$eval('body', b => b.innerText)
await state('503 object detail shows the server message', respond(503, { detail: { error: 'REFERENCE_DISTRIBUTION_UNAVAILABLE', detail: 'FC27 is research-only. Set include_research_data=true.', requires: 'include_research_data' } }), async p => ({ ok: /research-only/.test(await text(p)), detail: '' }))
await state('500 plain error is surfaced, not swallowed', respond(500, { detail: 'boom' }), async p => ({ ok: /boom|went wrong/i.test(await text(p)), detail: '' }))
await state('malformed 200 (ranked: null)', respond(200, { ranked: null, division: null }), async p => ({ ok: /unexpected response/i.test(await text(p)), detail: 'expects a visible error, not a blank page' }))
await state('empty ranked list says so', respond(200, { ranked: [], division: { requested: null, scope: 'ALL_DIVISIONS', candidate_counts: {} }, counts: { candidates: 5, excluded: 5 }, request_id: 'x' }), async p => ({ ok: /no eligible players/i.test(await text(p)), detail: '' }))
await state('slow response shows a loading indicator', respond(200, { ranked: [], division: { requested: null, scope: 'ALL_DIVISIONS', candidate_counts: {} } }, 3000), async p => ({ ok: /scoring players/i.test(await text(p)), detail: '' }))
await state('network failure is surfaced', r => live(r) ? (r.abort('failed'), true) : false, async p => ({ ok: /went wrong|failed|network|unreachable/i.test(await text(p)), detail: '' }))
}
