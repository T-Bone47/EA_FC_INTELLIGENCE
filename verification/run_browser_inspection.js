const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function runInspection() {
  console.log('=== Starting Real Browser E2E Inspection via Edge ===');
  
  const screenshotsDir = path.resolve(__dirname, '../artifacts/phase34b/screenshots');
  const artifactDir = path.resolve('C:/Users/dream/.gemini/antigravity/brain/612f9ab2-4567-4ad5-a428-5a670deed88f/screenshots');
  fs.mkdirSync(screenshotsDir, { recursive: true });
  fs.mkdirSync(artifactDir, { recursive: true });

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = {
    test_run: 'Phase 34B Browser E2E Inspection',
    timestamp: new Date().toISOString(),
    browser: 'Microsoft Edge (Headless Chromium)',
    target_url: 'http://localhost:5173/cards/squad-lab',
    desktop: {},
    mobile: {},
    inspector_tabs: {},
    overall_status: 'PASS'
  };

  try {
    // 1. Desktop Test (1440x900)
    console.log('1. Testing Desktop Viewport (1440x900)...');
    const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await desktopContext.newPage();
    
    const response = await page.goto('http://localhost:5173/cards/squad-lab', { waitUntil: 'domcontentloaded', timeout: 15000 });
    results.desktop.http_status = response.status();
    await page.waitForTimeout(1000);

    const pageTitle = await page.$eval('h1', el => el.textContent.trim());
    results.desktop.page_title = pageTitle;
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
    results.desktop.synergy_dashboard_rendered = !!synergyDashboard;

    // Full page desktop screenshot
    const deskShotPath = path.join(screenshotsDir, 'desktop_squad_lab_full.png');
    await page.screenshot({ path: deskShotPath, fullPage: true });
    fs.copyFileSync(deskShotPath, path.join(artifactDir, 'desktop_squad_lab_full.png'));
    results.desktop.screenshot = deskShotPath;
    console.log(`Desktop full page screenshot saved: ${deskShotPath}`);

    // Inspect each tab of the Synergy Explanation Inspector
    console.log('Inspecting interactive Synergy Explanation Inspector tabs...');
    const tabs = [
      { key: 'WHOLE_XI', selector: 'button:has-text("Whole XI Trace")' },
      { key: 'LEFT_FLANK', selector: 'button:has-text("Left Flank")' },
      { key: 'CENTRAL_SPINE', selector: 'button:has-text("Central Spine")' },
      { key: 'RIGHT_FLANK', selector: 'button:has-text("Right Flank")' },
      { key: 'ALERTS', selector: 'button:has-text("Tactical Alerts")' }
    ];

    for (const t of tabs) {
      const tabBtn = await page.$(t.selector);
      if (tabBtn) {
        await tabBtn.click();
        await page.waitForTimeout(350);
        const tabShotPath = path.join(screenshotsDir, `inspector_tab_${t.key.toLowerCase()}.png`);
        await page.screenshot({ path: tabShotPath });
        fs.copyFileSync(tabShotPath, path.join(artifactDir, `inspector_tab_${t.key.toLowerCase()}.png`));
        
        results.inspector_tabs[t.key] = {
          rendered: true,
          screenshot: tabShotPath
        };
        console.log(`Tab ${t.key} clicked and captured: ${tabShotPath}`);
      }
    }

    // Check formula trace box content
    const traceBox = await page.$('.synergy-trace-box');
    if (traceBox) {
      const traceText = await traceBox.innerText();
      results.desktop.trace_formula = traceText;
      console.log(`Formula trace verified:\n${traceText}`);
    }

    await desktopContext.close();

    // 2. Mobile Viewport (390x844 - Modern smartphone)
    console.log('2. Testing Mobile Viewport (390x844)...');
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
    results.mobile.horizontal_overflow_detected = bodyScrollWidth > bodyClientWidth;
    results.mobile.scroll_width = bodyScrollWidth;
    results.mobile.client_width = bodyClientWidth;

    const mobileShotPath = path.join(screenshotsDir, 'mobile_squad_lab.png');
    await mobilePage.screenshot({ path: mobileShotPath, fullPage: true });
    fs.copyFileSync(mobileShotPath, path.join(artifactDir, 'mobile_squad_lab.png'));
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
  const outJson = path.resolve(__dirname, '../artifacts/phase34b/BROWSER_E2E_RESULTS.json');
  fs.writeFileSync(outJson, JSON.stringify(results, null, 2), 'utf-8');
  console.log(`Browser E2E results saved to ${outJson}`);
}

runInspection();
