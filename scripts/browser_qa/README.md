# Browser QA
Run from the project root with the API on port 8011, a migrated isolated database,
the packaged FC26 and FC27 player snapshots loaded in the isolated local test environment, and a built frontend.

    npm install --prefix scripts/browser_qa --no-save puppeteer-core@24 axe-core@4
    node scripts/browser_qa/serve.mjs
    node --test scripts/browser_qa/qa.test.mjs

In another terminal set QA_CHROME to the browser executable, QA_OUT to the desired
JSON path and QA_SHOTS to the screenshots parent, then run `node scripts/browser_qa/qa.mjs`.
On supported Linux hosts the runner can also use an installed @sparticuz/chromium.
Reports include a unique directory per run. Infrastructure and failed required
assertions exit nonzero. Serious/critical axe violations carrying WCAG tags block
because they can prevent access to controls or content. Other axe findings are
warnings. The keyboard suite checks Tab order and visible focus. The mobile suite uses touch taps to select players. Undersized control measurements are diagnostic. The injected HTTP errors
are expected in the failure journeys. Uncaught page exceptions block in every journey.
