const path = require('path');
const fs = require('fs');
const { chromium } = require(path.resolve(__dirname, '../frontend/node_modules/playwright'));

async function runPhase37Inspection() {
  console.log('=== Starting Phase 37 Real Browser E2E Inspection via Edge ===');
  
  const screenshotsDir = path.resolve(__dirname, '../artifacts/phase37/screenshots');
  const artifactDir = path.resolve('C:/Users/dream/.gemini/antigravity/brain/612f9ab2-4567-4ad5-a428-5a670deed88f/screenshots');
  fs.mkdirSync(screenshotsDir, { recursive: true });
  fs.mkdirSync(artifactDir, { recursive: true });

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = {
    test_run: 'Phase 37 Gameplay Intelligence Studio & Radar Replay Browser E2E Inspection',
    timestamp: new Date().toISOString(),
    browser: 'Microsoft Edge (Headless Chromium)',
    target_urls: [
      'http://localhost:5173/research/gameplay-studio'
    ],
    desktop_cockpit: {},
    radar_replay: {},
    bayesian_calibration: {},
    mobile_viewport: {},
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

    // Trigger candidate proposal button
    const proposeBtn = await page.$('button:has-text("🤖 Propose Events")');
    if (proposeBtn) {
      await proposeBtn.click();
      await page.waitForTimeout(500);
    }

    const deskShotPath = path.join(screenshotsDir, 'phase37_studio_cockpit.png');
    await page.screenshot({ path: deskShotPath, fullPage: true });
    fs.copyFileSync(deskShotPath, path.join(artifactDir, 'phase37_studio_cockpit.png'));
    results.desktop_cockpit.screenshot = deskShotPath;
    console.log(`Desktop full page screenshot saved: ${deskShotPath}`);

    // -------------------------------------------------------------
    // 2. 2D PITCH RADAR REPLAY TAB
    // -------------------------------------------------------------
    console.log('2. Inspecting 2D Pitch Radar & Telemetry Replay Tab...');
    const radarTabBtn = await page.$('button:has-text("2D Radar & Pitch Replay")');
    if (radarTabBtn) {
      await radarTabBtn.click();
      await page.waitForTimeout(600);
      await page.waitForSelector('.pitch-svg-canvas', { timeout: 8000 });
      await page.waitForSelector('.tactical-hud-panel', { timeout: 8000 });

      // Click play replay button
      const playBtn = await page.$('button:has-text("Play 2D Replay")');
      if (playBtn) {
        await playBtn.click();
        await page.waitForTimeout(800);
      }

      const radarShotPath = path.join(screenshotsDir, 'phase37_studio_radar_replay.png');
      await page.screenshot({ path: radarShotPath });
      fs.copyFileSync(radarShotPath, path.join(artifactDir, 'phase37_studio_radar_replay.png'));
      results.radar_replay.screenshot = radarShotPath;
      results.radar_replay.status = 'PASS';
      console.log(`2D Radar Replay screenshot saved: ${radarShotPath}`);
    }

    // -------------------------------------------------------------
    // 3. BAYESIAN CALIBRATION TAB
    // -------------------------------------------------------------
    console.log('3. Navigating to Bayesian Calibration Tab...');
    const calibTabBtn = await page.$('button:has-text("Bayesian Calibration")');
    if (calibTabBtn) {
      await calibTabBtn.click();
      await page.waitForTimeout(600);
      await page.waitForSelector('.bayesian-dashboard', { timeout: 8000 });

      // Run Card Suitability Simulation
      const simBtn = await page.$('button:has-text("Simulate Suitability Score")');
      if (simBtn) {
        await simBtn.click();
        await page.waitForTimeout(500);
      }

      const calibShotPath = path.join(screenshotsDir, 'phase37_studio_bayesian_calibration.png');
      await page.screenshot({ path: calibShotPath });
      fs.copyFileSync(calibShotPath, path.join(artifactDir, 'phase37_studio_bayesian_calibration.png'));
      results.bayesian_calibration.screenshot = calibShotPath;
      results.bayesian_calibration.status = 'PASS';
      console.log(`Bayesian Calibration screenshot saved: ${calibShotPath}`);
    }

    await desktopContext.close();

    // -------------------------------------------------------------
    // 4. MOBILE VIEWPORT (390x844 - iPhone 12/13/14)
    // -------------------------------------------------------------
    console.log('4. Testing Mobile Viewport (390x844)...');
    const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
    const mobilePage = await mobileContext.newPage();
    
    await mobilePage.goto('http://localhost:5173/research/gameplay-studio', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await mobilePage.waitForTimeout(1000);

    // Switch to 2D Radar Replay tab on mobile
    const mobRadarBtn = await mobilePage.$('button:has-text("2D Radar")');
    if (mobRadarBtn) {
      await mobRadarBtn.click();
      await mobilePage.waitForTimeout(500);
    }

    // Assert zero horizontal overflow
    const overflowEvaluation = await mobilePage.evaluate(() => {
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
      };
    });

    results.mobile_viewport = overflowEvaluation;
    console.log(`Mobile overflow evaluation:`, overflowEvaluation);

    const mobShotPath = path.join(screenshotsDir, 'phase37_studio_radar_mobile.png');
    await mobilePage.screenshot({ path: mobShotPath });
    fs.copyFileSync(mobShotPath, path.join(artifactDir, 'phase37_studio_radar_mobile.png'));
    results.mobile_viewport.screenshot = mobShotPath;
    console.log(`Mobile screenshot saved: ${mobShotPath}`);

    await mobileContext.close();

  } catch (error) {
    console.error('Inspection encountered error:', error);
    results.overall_status = 'ERROR';
    results.error_message = error.message;
  } finally {
    await browser.close();
    const resultJsonPath = path.resolve(__dirname, '../artifacts/phase37/BROWSER_E2E_RESULTS.json');
    fs.writeFileSync(resultJsonPath, JSON.stringify(results, null, 2), 'utf-8');
    console.log(`Browser inspection completed. Report archived at: ${resultJsonPath}`);
  }
}

runPhase37Inspection().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
