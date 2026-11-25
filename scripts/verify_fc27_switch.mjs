import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const { chromium } = require(path.resolve(__dirname, '../frontend/node_modules/playwright'))

async function run() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  console.log('Navigating to http://localhost:5173/search...')
  await page.goto('http://localhost:5173/search', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)

  // Click the FC27 button in the top navigation bar
  const fc27Pill = page.locator('button:has-text("FC27"), a:has-text("FC27")').first()
  console.log('Clicking FC27 pill...')
  await fc27Pill.click()
  await page.waitForTimeout(2000)

  const shot = path.resolve(__dirname, '../artifacts/phase37/screenshots/db_connected_fc27_screen.png')
  await page.screenshot({ path: shot, fullPage: true })
  console.log('Saved FC27 screenshot:', shot)

  // Check if research opt-in checkbox is visible
  const optInCheckbox = page.locator('input[type="checkbox"]').first()
  if (await optInCheckbox.isVisible()) {
    console.log('Opting into FC27 research data...')
    await optInCheckbox.check()
    await page.waitForTimeout(2000)
    const shotWithPlayers = path.resolve(__dirname, '../artifacts/phase37/screenshots/db_connected_fc27_opted_in.png')
    await page.screenshot({ path: shotWithPlayers, fullPage: true })
    console.log('Saved FC27 opted-in screenshot:', shotWithPlayers)
  }

  await browser.close()
}

run().catch(err => {
  console.error(err)
  process.exit(1)
})
