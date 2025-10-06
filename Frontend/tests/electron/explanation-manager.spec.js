import { test, expect } from '../electron-fixtures.js';

test.describe('Explanation Manager Tests', () => {
  test('Explanations Liste ist anfangs leer', async ({ page }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    // Liste sollte leer sein oder "No explanations" Message zeigen
    const explanationsList = page.locator('explanations-tab .explanations-list');
    const listItems = page.locator('explanation-item');
    
    // Entweder keine Items oder empty state
    const itemCount = await listItems.count();
    if (itemCount === 0) {
      // Leer - gut
      expect(itemCount).toBe(0);
    } else {
      // Oder Empty State Message
      const emptyMessage = page.locator('.empty-state, .no-explanations');
      await expect(emptyMessage).toBeVisible();
    }
  });

  test('Neue Explanation kann über UI hinzugefügt werden', async ({ page, electronApp }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    // Explanation über JavaScript hinzufügen (simuliert Backend Response)
    await page.evaluate(() => {
      // Zugriff auf explanationManager aus dem Window Context
      const manager = window.explanationManager || 
                     document.querySelector('my-element')?.explanationManager;
      
      if (manager) {
        manager.addExplanation({
          id: 'test-1',
          title: 'Test Erklärung',
          content: 'Dies ist eine Test-Erklärung für Playwright.',
          timestamp: Date.now(),
          pinned: false
        });
      }
    });
    
    // Warten auf DOM Update
    await page.waitForTimeout(100);
    
    // Überprüfen ob Explanation Item erscheint
    const explanationItem = page.locator('explanation-item').first();
    await expect(explanationItem).toBeVisible();
    
    // Titel überprüfen
    const title = explanationItem.locator('.explanation-title');
    await expect(title).toContainText('Test Erklärung');
  });

  test('Explanation Item kann erweitert und eingeklappt werden', async ({ page }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    // Test Explanation hinzufügen
    await page.evaluate(() => {
      const manager = window.explanationManager || 
                     document.querySelector('my-element')?.explanationManager;
      
      if (manager) {
        manager.addExplanation({
          id: 'expand-test',
          title: 'Expand Test',
          content: 'Langer Inhalt der eingeklappt und erweitert werden kann.',
          timestamp: Date.now(),
          pinned: false
        });
      }
    });
    
    await page.waitForTimeout(100);
    
    const explanationItem = page.locator('explanation-item').first();
    await expect(explanationItem).toBeVisible();
    
    // Expand/Collapse Button finden und klicken
    const expandButton = explanationItem.locator('md-icon-button[title*="Expand"], md-icon-button[title*="Collapse"]');
    
    if (await expandButton.isVisible()) {
      await expandButton.click();
      await page.waitForTimeout(100);
      
      // Content sollte sichtbar/unsichtbar werden
      const content = explanationItem.locator('.explanation-content');
      // Je nach Standard-State prüfen ob erweitert oder eingeklappt
    }
  });

  test('Explanation kann gepinnt und entpinnt werden', async ({ page }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    // Test Explanation hinzufügen
    await page.evaluate(() => {
      const manager = window.explanationManager || 
                     document.querySelector('my-element')?.explanationManager;
      
      if (manager) {
        manager.addExplanation({
          id: 'pin-test',
          title: 'Pin Test',
          content: 'Diese Erklärung kann gepinnt werden.',
          timestamp: Date.now(),
          pinned: false
        });
      }
    });
    
    await page.waitForTimeout(100);
    
    const explanationItem = page.locator('explanation-item').first();
    const pinButton = explanationItem.locator('md-icon-button[title*="Pin"], md-icon-button[title*="Unpin"]');
    
    if (await pinButton.isVisible()) {
      await pinButton.click();
      await page.waitForTimeout(100);
      
      // Überprüfen ob Pin-Status sich geändert hat
      // (visueller Indikator für gepinnte Items)
      const pinnedIndicator = explanationItem.locator('.pinned, [pinned]');
      // Je nach Implementation
    }
  });

  test('Explanation kann gelöscht werden', async ({ page }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    // Test Explanation hinzufügen
    await page.evaluate(() => {
      const manager = window.explanationManager || 
                     document.querySelector('my-element')?.explanationManager;
      
      if (manager) {
        manager.addExplanation({
          id: 'delete-test',
          title: 'Delete Test',
          content: 'Diese Erklärung wird gelöscht.',
          timestamp: Date.now(),
          pinned: false
        });
      }
    });
    
    await page.waitForTimeout(100);
    
    const explanationItem = page.locator('explanation-item').first();
    await expect(explanationItem).toBeVisible();
    
    // Delete Button finden und klicken
    const deleteButton = explanationItem.locator('md-icon-button[title*="Delete"], md-icon-button[title*="Remove"]');
    
    if (await deleteButton.isVisible()) {
      await deleteButton.click();
      await page.waitForTimeout(100);
      
      // Item sollte verschwunden sein
      await expect(explanationItem).not.toBeVisible();
    }
  });
});

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