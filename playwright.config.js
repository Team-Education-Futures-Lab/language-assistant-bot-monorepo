const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './dashboard/tests/e2e',
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: 'http://localhost:3001',
    headless: true,
    viewport: { width: 1440, height: 1200 },
  },
  webServer: {
    command: 'npm --prefix dashboard start',
    url: 'http://localhost:3001',
    reuseExistingServer: true,
    timeout: 120000,
    env: {
      BROWSER: 'none',
      PORT_FOR_DEVELOPMENT: '3001',
      REACT_APP_API_BASE_URL: 'http://localhost:3001',
    },
  },
});
