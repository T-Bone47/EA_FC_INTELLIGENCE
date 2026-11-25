const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function runPhase35Inspection() {
  console.log('=== Starting Phase 35 Real Browser E2E Inspection via Edge ===');
  
  const screenshotsDir = path.resolve(__dirname, '../artifacts/phase35/screenshots');
  const artifactDir = path.resolve('C:/Users/dream/.gemini/antigravity/brain/612f9ab2-4567-4ad5-a428-5a670deed88f/screenshots');
  fs.mkdirSync(screenshotsDir, { recursive: true });
  fs.mkdirSync(artifactDir, { recursive: true });

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = {
    test_run: 'Phase 35 Full-Stack Browser E2E Inspection',
    timestamp: new Date().toISOString(),
    browser: 'Microsoft Edge (Headless Chromium)',
    target_urls: [
      'http://localhost:5173/cards/squad-lab',
      'http://localhost:5173/cards/performance'
    ],
    squad_lab_desktop: {},
    squad_lab_mobile: {},
    performance_lab_desktop: {},
    performance_lab_mobile: {},
    inspector_tabs: {},
    overall_status: 'PASS'
  };

  try {
    // -------------------------------------------------------------
    // 1. SQUAD LAB DESKTOP VIEWPORT (1440x900)
    // -------------------------------------------------------------
    console.log('1. Testing Squad Lab Desktop Viewport (1440x900)...');
    const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await desktopContext.newPage();
    
    const response = await page.goto('http://localhost:5173/cards/squad-lab', { waitUntil: 'domcontentloaded', timeout: 15000 });
    results.squad_lab_desktop.http_status = response.status();
    await page.waitForTimeout(1000);

    const pageTitle = await page.$eval('h1', el => el.textContent.trim());
    results.squad_lab_desktop.page_title = pageTitle;
    console.log(`Page title: ${pageTitle}`);

    // Click research opt-in checkbox
    console.log('Activating Local FC27 Research Mode...');
    await page.click('label.checkbox');
    await page.waitForTimeout(1200);

    // Click "Preview card squad" button to run evaluation
    console.log('Waiting for Preview button...');
    await page.waitForSelector('button:has-text("Preview card squad")', { timeout: 8000 });
    const previewBtn = await page.$('button:has-text("Preview card squad")');
    if (previewBtn) {
      console.log('Clicking "Preview card squad"...');
      await previewBtn.click();
      await page.waitForTimeout(1500);
    }

    // Verify Squad DNA / Synergy section is now rendered
    console.log('Waiting for .synergy-dashboard...');
    await page.waitForSelector('.synergy-dashboard', { timeout: 8000 });
    const synergyDashboard = await page.$('.synergy-dashboard');
    results.squad_lab_desktop.synergy_dashboard_rendered = !!synergyDashboard;

    // Full page desktop screenshot
    const deskShotPath = path.join(screenshotsDir, 'phase35_squad_lab_desktop_full.png');
    await page.screenshot({ path: deskShotPath, fullPage: true });
    fs.copyFileSync(deskShotPath, path.join(artifactDir, 'phase35_squad_lab_desktop_full.png'));
    results.squad_lab_desktop.screenshot = deskShotPath;
    console.log(`Desktop full page screenshot saved: ${deskShotPath}`);

    // Inspect each tab of the Synergy Explanation Inspector (including Phase 35 Tabs)
    console.log('Inspecting interactive Synergy Inspector tabs...');
    const tabs = [
      { key: 'WHOLE_XI', selector: 'button:has-text("Whole XI Trace")' },
      { key: 'LEFT_FLANK', selector: 'button:has-text("Left Flank")' },
      { key: 'CENTRAL_SPINE', selector: 'button:has-text("Central Spine")' },
      { key: 'RIGHT_FLANK', selector: 'button:has-text("Right Flank")' },
      { key: 'ALERTS', selector: 'button:has-text("Tactical Alerts")' },
      { key: 'PARTNERSHIPS', selector: 'button:has-text("Partnerships (V2)")' },
      { key: 'STABILITY', selector: 'button:has-text("Stability Lab")' }
    ];

    for (const t of tabs) {
      const tabBtn = await page.$(t.selector);
      if (tabBtn) {
        await tabBtn.click();
        await page.waitForTimeout(400);
        const tabShotPath = path.join(screenshotsDir, `phase35_tab_${t.key.toLowerCase()}.png`);
        await page.screenshot({ path: tabShotPath });
        fs.copyFileSync(tabShotPath, path.join(artifactDir, `phase35_tab_${t.key.toLowerCase()}.png`));
        
        results.inspector_tabs[t.key] = {
          rendered: true,
          screenshot: tabShotPath
        };
        console.log(`Tab ${t.key} clicked and captured: ${tabShotPath}`);
      } else {
        console.warn(`Tab button not found: ${t.selector}`);
        results.inspector_tabs[t.key] = { rendered: false };
      }
    }

    await desktopContext.close();

    // -------------------------------------------------------------
    // 2. SQUAD LAB MOBILE VIEWPORT (390x844 - iPhone 14 / modern phone)
    // -------------------------------------------------------------
    console.log('2. Testing Squad Lab Mobile Viewport (390x844)...');
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true
    });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto('http://localhost:5173/cards/squad-lab', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await mobilePage.waitForTimeout(1000);

    // Activate opt-in on mobile
    await mobilePage.click('label.checkbox');
    await mobilePage.waitForTimeout(1000);

    const mobPreviewBtn = await mobilePage.$('button:has-text("Preview card squad")');
    if (mobPreviewBtn) {
      await mobPreviewBtn.click();
      await mobilePage.waitForTimeout(1500);
    }

    await mobilePage.waitForSelector('.synergy-dashboard', { timeout: 8000 });

    const bodyScrollWidth = await mobilePage.evaluate(() => document.body.scrollWidth);
    const bodyClientWidth = await mobilePage.evaluate(() => document.body.clientWidth);
    results.squad_lab_mobile.horizontal_overflow_detected = bodyScrollWidth > bodyClientWidth;
    results.squad_lab_mobile.scroll_width = bodyScrollWidth;
    results.squad_lab_mobile.client_width = bodyClientWidth;

    const mobileShotPath = path.join(screenshotsDir, 'phase35_squad_lab_mobile.png');
    await mobilePage.screenshot({ path: mobileShotPath, fullPage: true });
    fs.copyFileSync(mobileShotPath, path.join(artifactDir, 'phase35_squad_lab_mobile.png'));
    results.squad_lab_mobile.screenshot = mobileShotPath;
    console.log(`Mobile screenshot saved: ${mobileShotPath}`);

    await mobileContext.close();

    // -------------------------------------------------------------
    // 3. PERFORMANCE EVIDENCE LAB DESKTOP (1440x900)
    // -------------------------------------------------------------
    console.log('3. Testing Performance Evidence Lab Desktop (1440x900)...');
    const perfContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const perfPage = await perfContext.newPage();
    const perfResp = await perfPage.goto('http://localhost:5173/cards/performance', { waitUntil: 'domcontentloaded', timeout: 15000 });
    results.performance_lab_desktop.http_status = perfResp.status();
    await perfPage.waitForTimeout(1000);

    // Activate research checkbox if present
    const perfCheckbox = await perfPage.$('label.checkbox');
    if (perfCheckbox) {
      console.log('Activating Performance research toggle...');
      await perfCheckbox.click();
      await perfPage.waitForTimeout(1200);
    }

    // Verify presence of Staging Database Status banner
    const stagingBanner = await perfPage.$('.evidence-lab');
    results.performance_lab_desktop.rendered = !!stagingBanner;

    const perfShotPath = path.join(screenshotsDir, 'phase35_performance_lab_desktop.png');
    await perfPage.screenshot({ path: perfShotPath, fullPage: true });
    fs.copyFileSync(perfShotPath, path.join(artifactDir, 'phase35_performance_lab_desktop.png'));
    results.performance_lab_desktop.screenshot = perfShotPath;
    console.log(`Performance Lab desktop screenshot saved: ${perfShotPath}`);

    await perfContext.close();

    // -------------------------------------------------------------
    // 4. PERFORMANCE EVIDENCE LAB MOBILE (390x844)
    // -------------------------------------------------------------
    console.log('4. Testing Performance Evidence Lab Mobile (390x844)...');
    const perfMobContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true
    });
    const perfMobPage = await perfMobContext.newPage();
    await perfMobPage.goto('http://localhost:5173/cards/performance', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await perfMobPage.waitForTimeout(1000);

    const perfMobCheckbox = await perfMobPage.$('label.checkbox');
    if (perfMobCheckbox) {
      await perfMobCheckbox.click();
      await perfMobPage.waitForTimeout(1000);
    }

    const perfMobShotPath = path.join(screenshotsDir, 'phase35_performance_lab_mobile.png');
    await perfMobPage.screenshot({ path: perfMobShotPath, fullPage: true });
    fs.copyFileSync(perfMobShotPath, path.join(artifactDir, 'phase35_performance_lab_mobile.png'));
    results.performance_lab_mobile.screenshot = perfMobShotPath;
    console.log(`Performance Lab mobile screenshot saved: ${perfMobShotPath}`);

    await perfMobContext.close();

  } catch (err) {
    console.error(`Browser inspection error: ${err.message}`);
    results.overall_status = 'ERROR';
    results.error = err.message;
  } finally {
    await browser.close();
  }

  // Save results JSON
  const outJson = path.resolve(__dirname, '../artifacts/phase35/BROWSER_E2E_RESULTS.json');
  fs.writeFileSync(outJson, JSON.stringify(results, null, 2), 'utf-8');
  console.log(`Browser E2E results saved to ${outJson}`);
}

runPhase35Inspection();
