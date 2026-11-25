import assert from 'node:assert/strict'
import {writeFile, readFile} from 'node:fs/promises'
import {randomUUID} from 'node:crypto'
import {chromium} from 'playwright'

const base = new URL(process.env.E2E_API_URL)
if (base.hostname !== '127.0.0.1') throw new Error('Use the loopback test server.')
const browser = await chromium.launch({executablePath:process.env.CHROME_PATH || undefined,
  args:['--disable-background-networking','--disable-component-update','--disable-sync','--disable-breakpad',
    '--disable-crash-reporter','--no-pings','--proxy-server=http://127.0.0.1:9',
    '--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1']})
const page = await browser.newPage({baseURL:base.origin,viewport:{width:390,height:844},serviceWorkers:'block'})
await page.context().route('**/*',route=>new URL(route.request().url()).origin===base.origin
  ?route.continue():route.abort('blockedbyclient'))
page.setDefaultTimeout(25000)
const errors=[]
page.on('pageerror',error=>errors.push(error.message))
const checks=[]
try {
  await page.goto('/cards/performance')
  await page.getByRole('heading',{name:'Performance Evidence Lab'}).waitFor()
  assert.equal(await page.getByLabel('Research card',{exact:true}).count(),0)
  const suffix=randomUUID()
  const signup=await page.request.post('/api/auth/signup',{data:{
    email:'performance-'+suffix+'@example.com', password:'Test-'+suffix,display_name:'Performance test'}})
  assert.equal(signup.status(),201)
  const token=(await signup.json()).access_token
  await page.evaluate(token=>localStorage.setItem('eafc.token',token),token)
  await page.reload()
  await page.getByLabel('Enable local FC27 performance research').check()
  const cohort=page.getByLabel('Research card',{exact:true})
  await cohort.locator('option').nth(100).waitFor({state:'attached'})
  assert.equal(await cohort.locator('option').count(),101)
  await page.getByLabel('Cohort',{exact:true}).selectOption('POSITION_CONTROL')
  assert.equal(await cohort.locator('option').count(),37)
  await page.getByLabel('Cohort',{exact:true}).selectOption('TOP_100')
  await cohort.selectOption({label:(await cohort.locator('option').filter({hasText:'Kylian Mbappé'}).textContent()).trim()})
  await page.getByLabel('Formation slot').selectOption('ST')
  await page.getByLabel('Game patch',{exact:true}).fill('1.2.0')
  await page.getByLabel('Assigned role').fill('Advanced Forward')
  await page.getByLabel('Second card').selectOption({label:'Erling Haaland · 239085'})
  await page.getByRole('button',{name:'Run comparison'}).click()
  await page.getByRole('columnheader',{name:'V3.2 fit'}).waitFor()
  assert.equal(await page.getByRole('columnheader',{name:'Observed per 90'}).count(),1)
  await page.getByText('Insufficient gameplay evidence',{exact:true}).last().waitFor()
  await page.getByLabel('Tactical profile').selectOption('HIGH_PRESS')
  assert.equal(await page.getByRole('columnheader',{name:'V3.2 fit'}).count(),0)
  checks.push('Opt-in, 100-item cohort, 36 controls, real V3.2 comparison, no measured winner, stale result invalidation')
  await page.getByLabel('Match date').fill('2026-11-10')
  await page.getByLabel('Match key',{exact:true}).fill('browser-'+suffix)
  await page.getByLabel('goals',{exact:true}).fill('0')
  await page.getByRole('checkbox',{name:/I recorded this match/}).check()
  await page.getByRole('button',{name:'Submit report'}).click()
  await page.getByText('1 report(s) saved.').waitFor()
  await page.getByText(/user submitted match · pending/).waitFor()
  await page.getByRole('button',{name:'Withdraw report'}).click()
  await page.getByText(/user submitted match · withdrawn/).waitFor()
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true)
  checks.push('Authenticated manual match submission with a reported zero, private pending state, owner withdrawal, 390px layout')
  let accessibility=null
  if(process.env.AXE_PATH){
    await page.evaluate(await readFile(process.env.AXE_PATH,'utf8'))
    const scan=await page.evaluate(async()=>{
      const result=await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})
      return {passes:result.passes.length,violations:result.violations.map(item=>({id:item.id,impact:item.impact}))}
    })
    accessibility=scan
    assert.deepEqual(scan.violations,[])
  }
  assert.deepEqual(errors,[])
  await writeFile(process.argv[2],JSON.stringify({checks,accessibility,uncaught_browser_errors:errors},null,2)+'\n')
} finally {
  await browser.close()
}
