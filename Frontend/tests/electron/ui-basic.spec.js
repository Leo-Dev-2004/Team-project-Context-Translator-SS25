import { test, expect } from '../electron-fixtures.js';

test.describe('UI Grundfunktionen', () => {
  test('App startet und zeigt Hauptfenster', async ({ page }) => {
    // Überprüfen ob die App gestartet ist
    await expect(page).toHaveTitle(/Context Translator/);
    
    // Überprüfen ob die UI-Component geladen ist
    await expect(page.locator('my-element')).toBeVisible();
  });

  test('Tab-Navigation funktioniert', async ({ page }) => {
    // Warten bis Tabs geladen sind
    await page.waitForSelector('md-tabs');
    
    // Setup Tab sollte standardmäßig aktiv sein (Tab 0)
    const setupTab = page.locator('md-primary-tab').first();
    await expect(setupTab).toHaveAttribute('active', '');
    
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    // Überprüfen ob Tab gewechselt hat
    await expect(explanationsTab).toHaveAttribute('active', '');
    await expect(setupTab).not.toHaveAttribute('active', '');
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

  test('Explanations Tab Inhalte sind sichtbar', async ({ page }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    // Manual Request Input sollte sichtbar sein
    const manualInput = page.locator('explanations-tab md-outlined-text-field[label="Explain a term"]');
    await expect(manualInput).toBeVisible();
    
    // Explain Button sollte sichtbar sein
    const explainButton = page.locator('explanations-tab md-filled-button:has-text("Explain")');
    await expect(explainButton).toBeVisible();
    
    // Explanations Liste sollte sichtbar sein
    const explanationsList = page.locator('explanations-tab .explanations-list');
    await expect(explanationsList).toBeVisible();
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

test.describe('Eingabefelder und Interaktionen', () => {
  test('Domain Input funktioniert', async ({ page }) => {
    await page.waitForSelector('setup-tab');
    
    const domainInput = page.locator('setup-tab md-outlined-text-field[label="Domain"] input');
    
    // Text eingeben
    await domainInput.fill('test-domain');
    await expect(domainInput).toHaveValue('test-domain');
    
    // Text löschen
    await domainInput.fill('');
    await expect(domainInput).toHaveValue('');
  });

  test('Manual Explanation Request funktioniert', async ({ page }) => {
    // Zu Explanations Tab wechseln
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    const manualInput = page.locator('explanations-tab md-outlined-text-field[label="Explain a term"] input');
    const explainButton = page.locator('explanations-tab md-filled-button:has-text("Explain")');
    
    // Begriff eingeben
    await manualInput.fill('Künstliche Intelligenz');
    await expect(manualInput).toHaveValue('Künstliche Intelligenz');
    
    // Button sollte klickbar sein
    await expect(explainButton).toBeEnabled();
    
    // Klick simulieren (ohne Backend wird kein Request gesendet)
    await explainButton.click();
    
    // Input sollte nach Request geleert werden (abhängig von Implementation)
    // await expect(manualInput).toHaveValue('');
  });

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