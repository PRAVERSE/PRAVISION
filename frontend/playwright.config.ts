import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  timeout: 60000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { 
        ...devices['Desktop Chrome'],
        baseURL: 'http://127.0.0.1:8000'
      },
    },
  ],
  webServer: {
    command: '..\\venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
    cwd: '../backend',
    url: 'http://127.0.0.1:8000',
    reuseExistingServer: true,
    timeout: 30000,
  },
});
