import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  workers: 1,
  use: {
    trace: 'retain-on-failure',
    headless: false,
    viewport: null,
    launchOptions: {
      slowMo: 1000,
      devtools: true
    }
  },
  projects: [
    {
      name: 'electron',
      testMatch: /electron\.spec\.js/,   // nur electron.spec.js
    },
    {
      name: 'web',
      testMatch: /ui\.spec\.js/,         // nur ui.spec.js
    }
  ],
  reporter: [
    ['list'],
    ['html']
  ]
});