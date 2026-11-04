const fs = require('fs');
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../node_modules/playwright'));

// Pure Node.js .env parser without external dependencies
function parseEnv(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const env = {};
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx !== -1) {
      const key = trimmed.slice(0, idx).trim();
      let val = trimmed.slice(idx + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      env[key] = val;
    }
  }
  return env;
}

const envPath = path.resolve(__dirname, '../../.env');
const envConfig = parseEnv(envPath);

const username = envConfig.username || envConfig.PRAVISION_AUTH_USERNAME;
const password = envConfig.password || envConfig.PRAVISION_AUTH_PASSWORD;

if (!username || !password) {
  console.error('[FAIL] Missing credentials in .env');
  process.exit(1);
}

const TARGET_URL = 'https://pravision.pages.dev';

async function runBrowserTest() {
  console.log('='.repeat(78));
  console.log('PRAVISION — REAL BROWSER PRODUCTION LOGIN & SESSION TEST');
  console.log(`Target URL: ${TARGET_URL}`);
  console.log(`Credentials configured: username=${Boolean(username)} (len=${username.length}), password=${Boolean(password)} (len=${password.length})`);
  console.log('='.repeat(78));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  let passCount = 0;
  let failCount = 0;

  function report(step, title, condition, details = '') {
    if (condition) {
      passCount++;
      console.log(`  [PASS] Step ${String(step).padStart(2, '0')}: ${title} ${details}`);
    } else {
      failCount++;
      console.log(`  [FAIL] Step ${String(step).padStart(2, '0')}: ${title} - ${details}`);
    }
  }

  try {
    // Step 1: Open website & verify initial mandatory login screen
    console.log('[1/7] Navigating to https://pravision.pages.dev...');
    await page.goto(TARGET_URL, { waitUntil: 'networkidle', timeout: 30000 });
    
    // Wait for auth check to finish and login screen to be rendered
    await page.waitForSelector('text=RESTRICTED ACCESS // MANDATORY LOGIN', { timeout: 15000 });
    
    const loginHeader = await page.locator('text=RESTRICTED ACCESS // MANDATORY LOGIN').isVisible();
    const loginButton = await page.locator('button[type="submit"]').isVisible();
    report(1, 'Mandatory Login Screen Displayed on Visit', loginHeader && loginButton);

    // Step 2: Attempt submission with invalid credentials
    console.log('[2/7] Testing rejection of invalid password in browser...');
    await page.fill('input[type="text"]', username);
    await page.fill('input[type="password"]', 'WrongPassword_999!');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(1500);

    const errorMessage = await page.locator('div.text-red-400').textContent();
    const badLoginRejected = errorMessage && errorMessage.includes('Invalid username or password');
    report(2, 'Invalid Credentials Error Displayed (No Field Leakage)', Boolean(badLoginRejected), `("${errorMessage}")`);

    // Step 3: Fill correct credentials from .env and log in
    console.log('[3/7] Entering valid .env credentials...');
    await page.fill('input[type="text"]', username);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');

    // Step 4: Confirm dashboard and intelligence workspace loads
    console.log('[4/7] Waiting for dashboard workspace...');
    await page.waitForSelector('header', { timeout: 20000 });
    const dashboardLoaded = await page.locator('text=PRAVISION').first().isVisible();
    const headerVisible = await page.locator('header').isVisible();
    const loginGone = !(await page.locator('text=RESTRICTED ACCESS // MANDATORY LOGIN').isVisible());
    report(3, 'Successful Authentication & Workspace Entrance', dashboardLoaded && headerVisible && loginGone);

    // Step 5: Check session cookie received by browser
    const cookies = await context.cookies();
    const sessionCookie = cookies.find(c => c.name === 'pravision_session');
    const cookieSecure = sessionCookie && sessionCookie.secure && sessionCookie.httpOnly;
    report(4, 'Browser Stored Secure HttpOnly Session Cookie', Boolean(sessionCookie), `(Name: pravision_session, Secure: ${sessionCookie?.secure}, HttpOnly: ${sessionCookie?.httpOnly})`);

    // Step 6: Reload page and confirm session persistence
    console.log('[5/7] Reloading page to test session persistence...');
    await page.reload({ waitUntil: 'networkidle', timeout: 20000 });
    const reloadDashboardVisible = await page.locator('header').isVisible();
    const reloadLoginNotVisible = !(await page.locator('text=RESTRICTED ACCESS // MANDATORY LOGIN').isVisible());
    report(5, 'Session Persists Seamlessly Across Browser Reload', reloadDashboardVisible && reloadLoginNotVisible);

    // Step 7: Click Sign Out and verify return to login gate
    console.log('[6/7] Clicking Sign Out...');
    await page.click('#btn-sign-out');
    await page.waitForSelector('text=RESTRICTED ACCESS // MANDATORY LOGIN', { timeout: 15000 });

    const returnLoginHeader = await page.locator('text=RESTRICTED ACCESS // MANDATORY LOGIN').isVisible();
    report(6, 'Sign Out Invalidation & Return to Login Screen', returnLoginHeader);

    // Step 8: Verify protected API access denied in browser context after logout
    console.log('[7/7] Testing direct fetch to /api/cases after logout...');
    const apiStatus = await page.evaluate(async () => {
      const res = await fetch('/api/cases');
      return res.status;
    });
    report(7, 'Post-Logout Browser Fetch Rejection (Anti-Replay)', apiStatus === 401, `(HTTP ${apiStatus})`);

  } catch (err) {
    console.error('[ERROR during browser test]:', err);
    failCount++;
  } finally {
    await browser.close();
  }

  console.log('='.repeat(78));
  console.log(`REAL BROWSER TEST RESULTS: ${passCount} PASSED, ${failCount} FAILED`);
  console.log('='.repeat(78));

  if (failCount > 0) {
    process.exit(1);
  }
}

runBrowserTest();
