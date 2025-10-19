import { _electron as electron } from 'playwright';
import { test as base } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const test = base.extend({
  electronApp: async ({}, use) => {
    // Launch Electron app
    const electronApp = await electron.launch({
      args: [path.join(__dirname, '../src/main.js')],
      env: {
        ...process.env,
        NODE_ENV: 'test'
      }
    });

    await use(electronApp);
    await electronApp.close();
  },

  page: async ({ electronApp }, use) => {
    // Get the first window
    const page = await electronApp.firstWindow();
    
    // Wait for the app to be ready
    await page.waitForLoadState('domcontentloaded');
    
    await use(page);
  },
});

export { expect } from '@playwright/test';