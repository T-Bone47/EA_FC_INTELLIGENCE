import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'

const outputDir = join(process.cwd(), '..', 'artifacts', 'stadium3', 'screenshots')
await mkdir(outputDir, { recursive: true })

const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

const browser = await chromium.launch({
  executablePath: chromePath,
  args: ['--disable-background-networking', '--no-sandbox']
})

const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 }
})

try {
  console.log('Navigating to Squad Lab...')
  await page.goto('http://localhost:5173/cards/squad-lab')
  await page.waitForTimeout(1500)

  // Capture desktop Squad Lab overview with new controls
  await page.screenshot({ path: join(outputDir, 'squad_lab_controls.png'), fullPage: true })
  console.log('Captured squad_lab_controls.png')

  // Inspect computed style of trigger
  const formationTrigger = page.locator('.stadium-select-trigger').first()
  if (await formationTrigger.count() > 0) {
    const styles = await formationTrigger.evaluate(el => {
      const computed = window.getComputedStyle(el)
      return {
        background: computed.backgroundColor,
        border: computed.borderColor,
        color: computed.color,
        height: computed.height,
        borderRadius: computed.borderRadius,
      }
    })
    console.log('Computed styles of StadiumSelect trigger:', JSON.stringify(styles, null, 2))

    // Click to open custom dropdown
    await formationTrigger.click()
    await page.waitForTimeout(300)
    await page.screenshot({ path: join(outputDir, 'squad_lab_dropdown_open.png') })
    console.log('Captured squad_lab_dropdown_open.png')

    // Close by clicking outside
    await page.locator('h2').first().click()
    await page.waitForTimeout(200)
  }

  // Open Combobox for PlayStyle+
  const combobox = page.locator('input[placeholder*="Finesse Shot"]').first()
  if (await combobox.count() > 0) {
    await combobox.focus()
    await combobox.fill('finesse')
    await page.waitForTimeout(300)
    await page.screenshot({ path: join(outputDir, 'squad_lab_combobox_open.png') })
    console.log('Captured squad_lab_combobox_open.png')
    await combobox.blur()
  }

  // Test Mobile Viewport 360px
  console.log('Testing mobile 360px viewport...')
  await page.setViewportSize({ width: 360, height: 800 })
  await page.waitForTimeout(500)
  await page.screenshot({ path: join(outputDir, 'squad_lab_mobile_360.png'), fullPage: true })
  console.log('Captured squad_lab_mobile_360.png')

  // Test Intelligence Studio
  console.log('Navigating to Intelligence Studio...')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('http://localhost:5173/intelligence')
  await page.waitForTimeout(1500)
  await page.screenshot({ path: join(outputDir, 'intelligence_controls.png'), fullPage: true })
  console.log('Captured intelligence_controls.png')

  // Test Discover / Search filters
  console.log('Navigating to Discover filters...')
  await page.goto('http://localhost:5173/search')
  await page.waitForTimeout(1500)
  await page.screenshot({ path: join(outputDir, 'search_filters.png'), fullPage: true })
  console.log('Captured search_filters.png')

  console.log('ALL SCREENSHOTS AND VISUAL VERIFICATION COMPLETED SUCCESSFULLY!')
} catch (err) {
  console.error('Error during verification:', err)
  process.exitCode = 1
} finally {
  await browser.close()
}
