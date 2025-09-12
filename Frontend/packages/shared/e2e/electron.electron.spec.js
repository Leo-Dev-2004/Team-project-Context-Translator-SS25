import { test, expect, _electron } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

// ES Module equivalent für __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Electron App E2E', () => {
    test.beforeEach(async ({ }, testInfo) => {
        try {
            console.log('Starting Electron test...');
  
            const electronApp = await _electron.launch({
                args: [path.resolve(__dirname, '../../electron/src/main.js')],
                env: {
                    NODE_ENV: 'development',
                    DISPLAY: ':0',
                    VITE_DEV_SERVER_URL: 'http://localhost:5173' // Wichtig: Dev Server URL
                }
            });

            // Warte auf Main Process
            await electronApp.evaluate(({ app }) => {
                return new Promise((resolve) => {
                    if (app.isReady()) resolve();
                    else app.on('ready', resolve);
                });
            });

            // Hole Renderer Process (Fenster)
            const page = await electronApp.firstWindow();
            console.log('Window obtained, waiting for load...');

            // Warte auf Renderer
            await page.waitForLoadState('load');
            await page.waitForLoadState('networkidle');
            console.log('Window loaded');

            // Debug: Prüfe DOM
            const html = await page.evaluate(() => document.documentElement.innerHTML);
            console.log('Current HTML:', html);

            testInfo.window = page;
            testInfo.electronApp = electronApp;

        } catch (error) {
            console.error('Setup failed:', error);
            throw error;
        }
    });

    test.afterEach(async ({ }, testInfo) => {
        if (testInfo.electronApp) {
            await testInfo.electronApp.close().catch(console.error);
        }
    });

    // Rest of the tests remain similar as in web-version test, just replace 'page' with 'testInfo.window'
    test('should add explanation on button click', async ({ }, testInfo) => {
        const window = testInfo.window;
    
        const addTestButton = await window.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addTestButton.click();

        const explanation = await window.waitForSelector('explanation-item', { timeout: 15000 });
        expect(explanation).toBeTruthy();
    });

    // Debug Test für Buttons
    test('Debug: should log all icon button names in explanation item after creation', async ({ }, testInfo) => {
        const window = testInfo.window;
    
        const addTestButton = await window.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addTestButton.click();

        const explanationItem = window.locator('explanation-item').first();
        const buttons = window.locator('explanation-item >>> md-icon-button');
        const buttonCount = await buttons.count();
        console.log('Gefundene md-icon-buttons:', buttonCount);

        for (let i = 0; i < buttonCount; i++) {
            const icon = buttons.nth(i).locator('md-icon');
            const text = await icon.textContent();
            console.log(`Button ${i + 1}:`, text && text.trim());
        }

        expect(buttonCount).toBeGreaterThan(0);
    });

    test('should remove explanation when delete clicked', async ({ }, testInfo) => {
        const window = testInfo.window;
    
        const addTestButton = await window.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addTestButton.click();

        const explanationItem = await window.waitForSelector('explanation-item', { timeout: 15000 });

        let deleteButton;
        try {
            const deleteButton = await window.locator('explanation-item >>> md-icon-button:has(md-icon:text("delete"))').first();
        } catch {
            deleteButton = await window.waitForSelector('explanation-item md-icon-button:has(md-icon:text("delete"))', { timeout: 5000 });
        }
        await deleteButton.click();

        await expect(window.locator('explanation-item')).toHaveCount(0);
    });

    test('should pin explanation', async ({ }, testInfo) => {
        const window = testInfo.window;
    
        const button = await window.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await button.click();

        const pinButton = await window.waitForSelector('explanation-item button.pin', { timeout: 15000 });
        await pinButton.click();

        await expect(window.locator('explanation-item[isPinned="true"]')).toHaveCount(1);
    });

    test('should clear unpinned explanations but keep pinned ones', async ({ }, testInfo) => {
        const window = testInfo.window;
    
        const addButton = await window.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addButton.click();
        await addButton.click();

        const pinButton = await window.waitForSelector('explanation-item >> nth=0 >> button.pin', { timeout: 15000 });
        await pinButton.click();

        const clearButton = await window.waitForSelector('md-text-button:has-text("Clear All")', { timeout: 15000 });
        await clearButton.click();

        await expect(window.locator('explanation-item')).toHaveCount(1);
        await expect(window.locator('explanation-item[isPinned="true"]')).toHaveCount(1);
    });

    test('should save setup configuration', async ({ }, testInfo) => {
        const window = testInfo.window;
    
        await window.click('md-primary-tab:nth-child(1)');
        await window.fill('md-outlined-text-field', 'Software Developer');

        await window.click('md-outlined-select');
        await window.click('md-select-option[value="de"]');

        await window.click('md-switch');
        await window.click('md-filled-button:has-text("Save Configuration")');

        await expect(window.locator('md-outlined-text-field')).toHaveValue('Software Developer');
        await expect(window.locator('md-outlined-select')).toHaveValue('de');
        await expect(window.locator('md-switch')).toBeChecked();
    });
});