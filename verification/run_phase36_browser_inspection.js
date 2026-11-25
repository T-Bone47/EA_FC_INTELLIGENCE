const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function runPhase36Inspection() {
  console.log('=== Starting Phase 36 Real Browser E2E Inspection via Edge ===');
  
  const screenshotsDir = path.resolve(__dirname, '../artifacts/phase36/screenshots');
  const artifactDir = path.resolve('C:/Users/dream/.gemini/antigravity/brain/612f9ab2-4567-4ad5-a428-5a670deed88f/screenshots');
  fs.mkdirSync(screenshotsDir, { recursive: true });
  fs.mkdirSync(artifactDir, { recursive: true });

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = {
    test_run: 'Phase 36 Gameplay Intelligence Studio Browser E2E Inspection',
    timestamp: new Date().toISOString(),
    browser: 'Microsoft Edge (Headless Chromium)',
    target_urls: [
      'http://localhost:5173/research/gameplay-studio'
    ],
    desktop_cockpit: {},
    inspector_focused: {},
    challenges_tab: {},
    quality_tab: {},
    mobile: {},
    overall_status: 'PASS'
  };

  try {
    // -------------------------------------------------------------
    // 1. DESKTOP COCKPIT VIEWPORT (1440x900)
    // -------------------------------------------------------------
    console.log('1. Testing Desktop Studio Viewport (1440x900)...');
    const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await desktopContext.newPage();
    
    const response = await page.goto('http://localhost:5173/research/gameplay-studio', { waitUntil: 'domcontentloaded', timeout: 15000 });
    results.desktop_cockpit.http_status = response.status();
    await page.waitForTimeout(1000);

    const pageTitle = await page.$eval('h1', el => el.textContent.trim());
    results.desktop_cockpit.page_title = pageTitle;
    console.log(`Page title: ${pageTitle}`);

    // Verify presence of studio components
    await page.waitForSelector('[data-testid="gameplay-studio"]', { timeout: 8000 });
    await page.waitForSelector('.studio-cockpit-grid', { timeout: 8000 });

    const deskShotPath = path.join(screenshotsDir, 'phase36_studio_cockpit_desktop.png');
    await page.screenshot({ path: deskShotPath, fullPage: true });
    fs.copyFileSync(deskShotPath, path.join(artifactDir, 'phase36_studio_cockpit_desktop.png'));
    results.desktop_cockpit.screenshot = deskShotPath;
    console.log(`Desktop full page screenshot saved: ${deskShotPath}`);

    // -------------------------------------------------------------
    // 2. FOCUSED INSPECTOR & EVENT TIMELINE
    // -------------------------------------------------------------
    console.log('2. Inspecting Tactical Timeline & Event Pins...');
    const pin = await page.$('.event-pin-marker');
    if (pin) {
      await pin.click();
      await page.waitForTimeout(400);
    }

    // Click "+ Tag Observation" button
    const tagBtn = await page.$('button:has-text("+ Tag Observation")');
    if (tagBtn) {
      await tagBtn.click();
      await page.waitForTimeout(400);
    }

    const inspectorShotPath = path.join(screenshotsDir, 'phase36_studio_inspector_focused.png');
    await page.screenshot({ path: inspectorShotPath });
    fs.copyFileSync(inspectorShotPath, path.join(artifactDir, 'phase36_studio_inspector_focused.png'));
    results.inspector_focused.screenshot = inspectorShotPath;
    console.log(`Inspector focused screenshot saved: ${inspectorShotPath}`);

    // Close modal if open
    const cancelBtn = await page.$('button:has-text("Cancel")');
    if (cancelBtn) {
      await cancelBtn.click();
      await page.waitForTimeout(300);
    }

    // -------------------------------------------------------------
    // 3. PREDICTION CHALLENGES TAB
    // -------------------------------------------------------------
    console.log('3. Navigating to Prediction Challenges Tab...');
    const challengeTabBtn = await page.$('button:has-text("Prediction Challenges")');
    if (challengeTabBtn) {
      await challengeTabBtn.click();
      await page.waitForTimeout(500);
      await page.waitForSelector('.challenge-table', { timeout: 5000 });

      const chalShotPath = path.join(screenshotsDir, 'phase36_studio_challenges_tab.png');
      await page.screenshot({ path: chalShotPath });
      fs.copyFileSync(chalShotPath, path.join(artifactDir, 'phase36_studio_challenges_tab.png'));
      results.challenges_tab.screenshot = chalShotPath;
      console.log(`Prediction Challenges screenshot saved: ${chalShotPath}`);
    }

    // -------------------------------------------------------------
    // 4. EVIDENCE QUALITY AUDIT TAB
    // -------------------------------------------------------------
    console.log('4. Navigating to Evidence Quality Audit Tab...');
    const qualityTabBtn = await page.$('button:has-text("Evidence Quality Audit")');
    if (qualityTabBtn) {
      await qualityTabBtn.click();
      await page.waitForTimeout(500);

      const qualShotPath = path.join(screenshotsDir, 'phase36_studio_quality_tab.png');
      await page.screenshot({ path: qualShotPath });
      fs.copyFileSync(qualShotPath, path.join(artifactDir, 'phase36_studio_quality_tab.png'));
      results.quality_tab.screenshot = qualShotPath;
      console.log(`Evidence Quality Audit screenshot saved: ${qualShotPath}`);
    }

    await desktopContext.close();

    // -------------------------------------------------------------
    // 5. MOBILE VIEWPORT (390x844 - iPhone 14)
    // -------------------------------------------------------------
    console.log('5. Testing Mobile Viewport (390x844)...');
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true
    });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto('http://localhost:5173/research/gameplay-studio', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await mobilePage.waitForTimeout(1000);

    const bodyScrollWidth = await mobilePage.evaluate(() => document.body.scrollWidth);
    const bodyClientWidth = await mobilePage.evaluate(() => document.body.clientWidth);
    results.mobile.horizontal_overflow_detected = bodyScrollWidth > bodyClientWidth;
    results.mobile.scroll_width = bodyScrollWidth;
    results.mobile.client_width = bodyClientWidth;

    const mobileShotPath = path.join(screenshotsDir, 'phase36_studio_mobile.png');
    await mobilePage.screenshot({ path: mobileShotPath, fullPage: true });
    fs.copyFileSync(mobileShotPath, path.join(artifactDir, 'phase36_studio_mobile.png'));
    results.mobile.screenshot = mobileShotPath;
    console.log(`Mobile screenshot saved: ${mobileShotPath}`);

    await mobileContext.close();

  } catch (err) {
    console.error(`Browser inspection error: ${err.message}`);
    results.overall_status = 'ERROR';
    results.error = err.message;
  } finally {
    await browser.close();
  }

  // Save results JSON
  const outJson = path.resolve(__dirname, '../artifacts/phase36/BROWSER_E2E_RESULTS.json');
  fs.writeFileSync(outJson, JSON.stringify(results, null, 2), 'utf-8');
  console.log(`Browser E2E results saved to ${outJson}`);
}

runPhase36Inspection();
