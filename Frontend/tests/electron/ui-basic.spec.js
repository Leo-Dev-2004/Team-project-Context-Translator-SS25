import { test, expect } from '../electron-fixtures.js';

test.describe('UI Grundfunktionen', () => {
  test('App startet und zeigt Hauptfenster', async ({ page }) => {
    // Überprüfen ob die App gestartet ist
    await expect(page).toHaveTitle(/Context Translator/);
    
    // Überprüfen ob die UI-Component geladen ist
    await expect(page.locator('my-element')).toBeVisible();
  });


  test('Setup Tab Inhalte sind sichtbar', async ({ page }) => {
    // Setup Tab sollte standardmäßig aktiv sein
    await page.waitForSelector('setup-tab');
    
    // Domain Input sollte sichtbar sein
    const domainInput = page.locator('setup-tab md-outlined-text-field[label="Domain"]');
    await expect(domainInput).toBeVisible();
    
    // Explanation Style Select sollte sichtbar sein
    const styleSelect = page.locator('setup-tab md-outlined-select[label="Explanation Style"]');
    await expect(styleSelect).toBeVisible();
    
    // Speichern Button sollte sichtbar sein
    const saveButton = page.locator('setup-tab md-filled-button:has-text("Save Settings")');
    await expect(saveButton).toBeVisible();
  });
});

test.describe('Status Bar', () => {
  test('Status Bar ist sichtbar und zeigt Status an', async ({ page }) => {
    await page.waitForSelector('status-bar');
    
    // Server Status sollte angezeigt werden
    const serverStatus = page.locator('status-bar .server-status');
    await expect(serverStatus).toBeVisible();
    
    // Microphone Status sollte angezeigt werden  
    const micStatus = page.locator('status-bar .microphone-status');
    await expect(micStatus).toBeVisible();
  });
});


test.describe('Explanation Style Auswahl', () => {
  test('Explanation Style Select funktioniert', async ({ page }) => {
    await page.waitForSelector('setup-tab');
    
    const styleSelect = page.locator('setup-tab md-outlined-select[label="Explanation Style"]');
    
    // Select öffnen
    await styleSelect.click();
    
    // Warten auf Optionen
    await page.waitForSelector('md-select-option');
    
    // Eine Option auswählen
    const detailedOption = page.locator('md-select-option[value="detailed"]');
    if (await detailedOption.isVisible()) {
      await detailedOption.click();
    }
  });
});