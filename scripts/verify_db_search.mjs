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
  await page.waitForTimeout(2000)

  const shot1 = path.resolve(__dirname, '../artifacts/phase37/screenshots/db_connected_search_fc27.png')
  await page.screenshot({ path: shot1, fullPage: true })
  console.log('Saved screenshot 1:', shot1)

  // Check what text is on the page
  const text = await page.textContent('body')
  console.log('Page has "Database not connected":', text.includes('Database not connected'))
  console.log('Page has "Local Research Available":', text.includes('Local Research Available'))

  // Click on "Opt in to research data" or checkbox if present
  const checkbox = page.locator('input[type="checkbox"]').first()
  if (await checkbox.isVisible()) {
    console.log('Checking research opt-in checkbox...')
    await checkbox.check()
    await page.waitForTimeout(2000)
    const shotOptIn = path.resolve(__dirname, '../artifacts/phase37/screenshots/db_connected_optin_fc27.png')
    await page.screenshot({ path: shotOptIn, fullPage: true })
    console.log('Saved opt-in screenshot:', shotOptIn)
  }

  // Switch to FC26
  const fc26Btn = page.getByRole('button', { name: /FC26/i }).first()
  if (await fc26Btn.isVisible()) {
    console.log('Clicking FC26 toggle...')
    await fc26Btn.click()
    await page.waitForTimeout(2000)
    const shot2 = path.resolve(__dirname, '../artifacts/phase37/screenshots/db_connected_search_fc26.png')
    await page.screenshot({ path: shot2, fullPage: true })
    console.log('Saved FC26 screenshot:', shot2)
  }

  await browser.close()
  console.log('Browser test complete!')
}

run().catch(err => {
  console.error('Browser test failed:', err)
  process.exit(1)
})
