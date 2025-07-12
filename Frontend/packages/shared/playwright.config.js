import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: {
    // Make sure this matches your development server URL
    baseURL: 'http://localhost:5175',
    // Add longer timeouts for element operations
    actionTimeout: 10000,
    // Add timeout for expect operations
    expect: {
      timeout: 10000
    }
  },
  // Disable automatic web server start - we'll run it manually
  webServer: null,
  // Increase timeout for local development
  timeout: 30000,
  // Add project name for workspace usage
  name: 'shared',
  // Add testMatch to ensure only e2e tests are run
  testMatch: ['e2e/**/*.spec.js'],
});
