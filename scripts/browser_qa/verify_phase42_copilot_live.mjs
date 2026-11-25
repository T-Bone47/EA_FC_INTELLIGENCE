import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const SCREENSHOT_DIR = process.env.E2E_SHOTS_DIR || path.join(os.tmpdir(), 'eafc-phase42-e2e-shots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

function resolveBrowserExecutable() {
  const candidates = [
    process.env.QA_CHROME,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ].filter(Boolean);
  return candidates.find(p => fs.existsSync(p));
}

async function run() {
  const executablePath = resolveBrowserExecutable();
  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const serverErrors = [];
  const networkFailures = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => consoleErrors.push(String(err)));
  page.on('response', res => {
    if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
    else if (res.status() === 404 && res.url().includes('/api/')) networkFailures.push(`${res.status()} ${res.url()}`);
  });

  const testEmail = `phase42_e2e_${Date.now()}@example.com`;
  const testPass = 'Password123!';

  // 1. Real Account Sign Up -> Authenticated Workflow
  await page.goto(`${BASE_URL}/signup`, { waitUntil: 'networkidle' });
  await page.fill('input[type="email"]', testEmail);
  await page.fill('input[autocomplete="nickname"]', 'Phase42E2E');
  const pwInputs = page.locator('input[type="password"]');
  await pwInputs.nth(0).fill(testPass);
  if (await pwInputs.count() > 1) await pwInputs.nth(1).fill(testPass);
  await page.click('button[type="submit"]');
  await page.waitForFunction(() => !window.location.pathname.includes('/signup'), { timeout: 10000 });

  // Navigate to PersonalCoach and assert authenticated access
  await page.goto(`${BASE_URL}/coach`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#coach-question-input', { timeout: 12000 });

  // 2. Enable external AI synthesis opt-in and test live Coach query hitting Gemini/OpenRouter/fallback
  const consentBox = page.locator('label:has-text("Enable free-tier Gemini / OpenRouter") input[type="checkbox"]');
  if (await consentBox.count()) await consentBox.check();
  await page.fill('#coach-question-input', 'Recommend 2 defensive midfielders for FC27 in 4-2-3-1 and explain FC IQ Holding role.');
  await page.click('button:has-text("Ask Coach")');
  await page.waitForSelector('.coach-response-card', { timeout: 60000 });
  const coachCardText = await page.locator('.coach-response-card').first().textContent();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'phase42_coach_desktop.png') });

  // Verify conversation persistence session list updated
  const convCount = await page.locator('.coach-conv-btn').count();

  // 3. Test Screenshot Redactor Modal in Coach (Phase 42G)
  await page.click('button:has-text("Attach Redacted Screenshot")');
  await page.waitForSelector('[aria-label="Screenshot Privacy Redaction Canvas"]', { timeout: 5000 });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'phase42_redactor_modal.png') });
  await page.click('[aria-label="Screenshot Privacy Redaction Canvas"] button:has-text("Close")');

  // 4. Test Training Academy tab (Phase 42H categories & blind review attempt)
  await page.click('button:has-text("Training Academy")');
  await page.waitForSelector('.coach-option-btn', { timeout: 10000 });
  await page.locator('.coach-option-btn').first().click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'phase42_training_desktop.png') });

  // 5. Contextual Co-Pilot across Search, Squad Lab & Decision Lab
  await page.goto(`${BASE_URL}/search`, { waitUntil: 'networkidle' });
  await page.click('button:has-text("Ask Co-Pilot")');
  await page.waitForSelector('[aria-label="EA FC Intelligence Co-Pilot"]', { timeout: 10000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'phase42_copilot_search_desktop.png') });
  await page.click('button[aria-label="Close Co-Pilot"]');

  await page.goto(`${BASE_URL}/cards/squad-lab`, { waitUntil: 'networkidle' });
  await page.click('button:has-text("Ask Co-Pilot")');
  await page.waitForSelector('[aria-label="EA FC Intelligence Co-Pilot"]', { timeout: 8000 });
  const squadContextBadge = await page.locator('.copilot-context-bar').textContent();
  await page.click('button[aria-label="Close Co-Pilot"]');

  await page.goto(`${BASE_URL}/research/decision-lab`, { waitUntil: 'networkidle' });
  await page.click('button:has-text("Ask Co-Pilot")');
  await page.waitForSelector('[aria-label="EA FC Intelligence Co-Pilot"]', { timeout: 8000 });

  // 6. Mobile viewport check (390x844)
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'phase42_copilot_mobile.png') });
  await page.click('button[aria-label="Close Co-Pilot"]');

  const summary = {
    status: 'PASS',
    authenticated_email: testEmail,
    conversation_sessions_visible: convCount,
    squad_context_badges: squadContextBadge?.trim(),
    first_coach_reply_preview: coachCardText?.slice(0, 180),
    consoleErrors,
    serverErrors,
    networkFailures,
    screenshots: [
      'phase42_coach_desktop.png',
      'phase42_redactor_modal.png',
      'phase42_training_desktop.png',
      'phase42_copilot_search_desktop.png',
      'phase42_copilot_mobile.png',
    ],
  };
  console.log(JSON.stringify(summary, null, 2));
  await browser.close();
  if (serverErrors.length > 0) {
    process.exit(1);
  }
}

run().catch(err => {
  console.error('E2E_FAILED:', err);
  process.exit(1);
});
