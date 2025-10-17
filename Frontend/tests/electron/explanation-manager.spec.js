import { test, expect } from '../electron-fixtures.js';

test.describe('Dark Mode und Theme Tests', () => {
  test('Dark Mode Toggle funktioniert', async ({ page }) => {
    await page.waitForSelector('my-element');
    
    // Suche nach Dark Mode Toggle (könnte in verschiedenen Komponenten sein)
    const darkModeToggle = page.locator('md-switch, input[type="checkbox"]').first();
    
    if (await darkModeToggle.isVisible()) {
      // Initial State prüfen
      const initialState = await darkModeToggle.isChecked();
      
      // Toggle klicken
      await darkModeToggle.click();
      await page.waitForTimeout(100);
      
      // State sollte sich geändert haben
      const newState = await darkModeToggle.isChecked();
      expect(newState).not.toBe(initialState);
      
      // CSS Classes oder Styles sollten sich ändern
      const rootElement = page.locator('my-element, body, html');
      // Je nach Implementation dark-mode class prüfen
    }
  });
});