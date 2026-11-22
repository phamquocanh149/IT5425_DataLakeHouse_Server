import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: process.env.PORTAL_URL || 'http://127.0.0.1:8010',
    channel: 'chrome',
    viewport: {width: 1440, height: 1000},
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
