import { test, expect } from '@playwright/test';

test.describe('Web App E2E', () => {
    test.beforeEach(async ({ page }) => {
        // Warte auf App-Start
        await page.goto('http://localhost:5173');
        
        // Warte auf initiales Laden
        await page.waitForLoadState('domcontentloaded');
        await page.waitForLoadState('networkidle');
        
        // Warte auf h1 mit Text als Indikator für geladene App
        await page.waitForSelector('h1:has-text("Context Translator")', { state: 'visible' });
        
        // Navigiere zum Explanations Tab
        await page.click('md-primary-tab:nth-child(2)');
        await page.waitForSelector('.explanations-panel', { state: 'visible' });
    });

    test('should add explanation on button click', async ({ page }) => {
        const addTestButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addTestButton.click();

        const explanation = await page.waitForSelector('explanation-item', { timeout: 15000 });
        expect(explanation).toBeTruthy();
    });

    test('should remove explanation when delete clicked', async ({ page }) => {
        const addTestButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addTestButton.click();

        const explanationItem = await page.waitForSelector('explanation-item', { timeout: 15000 });

        const deleteButton = await page.getByRole('button', { name: 'close' });
        await deleteButton.click();
        
        // Warte auf Animation und Entfernung des Elements
        await page.waitForTimeout(1000); // Warte auf Animation
        await expect(page.locator('explanation-item')).toHaveCount(0, { timeout: 15000 });
    });

    test('should pin explanation', async ({ page }) => {
        const button = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await button.click();

        const pinButton = await page.getByRole('button', { name: 'push_pin' });
        await pinButton.click();

        await page.waitForTimeout(1000); // Warte auf Animation
        await expect(page.locator('explanation-item[isPinned="true"]')).toHaveCount(1, { timeout: 15000 });
    });

    test('should clear unpinned explanations but keep pinned ones', async ({ page }) => {
        const addButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
        await addButton.click();
        await addButton.click();

        const pinButton = await page.getByRole('button', { name: 'push_pin' });
        await pinButton.click();
        await page.waitForTimeout(1000); // Warte auf Pin-Animation

        const clearButton = await page.getByRole('button', { name: 'delete Clear All' });
        await clearButton.click();
        await page.waitForTimeout(1000); // Warte auf Clear-Animation

        await expect(page.locator('explanation-item')).toHaveCount(1, { timeout: 15000 });
        await expect(page.locator('explanation-item[isPinned="true"]')).toHaveCount(1, { timeout: 15000 });
    });

    test('should save setup configuration', async ({ page }) => {
        await page.click('md-primary-tab:nth-child(1)');
        await page.fill('md-outlined-text-field', 'Software Developer');

        await page.click('md-outlined-select');
        await page.click('md-select-option[value="de"]');

        await page.click('md-switch');
        await page.click('md-filled-button:has-text("Save Configuration")');

        await expect(page.locator('md-outlined-text-field')).toHaveValue('Software Developer');
        await expect(page.locator('md-outlined-select')).toHaveValue('de');
        await expect(page.locator('md-switch')).toBeChecked();
    });
});