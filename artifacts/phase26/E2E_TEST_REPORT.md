# E2E evidence

The browser QA lifecycle passed 10 Node subprocess scenarios covering successful exit, warnings, failed assertions, failed page load, startup crash, invalid URL, missing or empty suite, missing screenshot and cleanup failure. The actual CLI returned 1 because puppeteer-core is unavailable and wrote browser_startup.json. No browser session or screenshot exists for this run. No viewport result was measured.

The intended CI run uses a disposable PostgreSQL service, migrates twice, builds the frontend, starts FastAPI and exercises Chromium at 1280×900, 768×1024 and 390×844. The browser subprocess status is the job step status. CI execution, browser recommendation/compare/what-if, keyboard and touch, failure journeys, stale transport, and verification from API to DB remain blocked.
