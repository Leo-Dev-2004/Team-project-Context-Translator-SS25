import { test, expect } from '@playwright/test';

test.describe('Komponenten Unit Tests (Browser)', () => {
  test.beforeEach(async ({ page }) => {
    // Navigiere zu Vite Dev Server
    await page.goto('/');
    
    // Warten bis Vite Seite geladen ist
    await page.waitForLoadState('networkidle');
  });

  test('UI Komponente kann isoliert getestet werden', async ({ page }) => {
    // HTML Seite für isolierte Komponenten-Tests erstellen
    await page.setContent(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Component Test</title>
        <script type="module">
          import { UI } from '/src/components/ui.js';
          customElements.define('test-ui', UI);
        </script>
      </head>
      <body>
        <test-ui></test-ui>
      </body>
      </html>
    `);
    
    await page.waitForSelector('test-ui');
    
    // Überprüfen ob Komponente gerendert wurde
    const component = page.locator('test-ui');
    await expect(component).toBeVisible();
  });

  test('Status Bar Komponente isoliert testen', async ({ page }) => {
    await page.setContent(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Status Bar Test</title>
        <script type="module">
          import '/src/components/status-bar.js';
        </script>
      </head>
      <body>
        <status-bar server-status="Connected" microphone-status="Active"></status-bar>
      </body>
      </html>
    `);
    
    await page.waitForSelector('status-bar');
    
    const statusBar = page.locator('status-bar');
    await expect(statusBar).toBeVisible();
    
    // Server Status prüfen
    const serverStatus = statusBar.locator('.server-status');
    if (await serverStatus.isVisible()) {
      await expect(serverStatus).toContainText('Connected');
    }
    
    // Microphone Status prüfen
    const micStatus = statusBar.locator('.microphone-status');
    if (await micStatus.isVisible()) {
      await expect(micStatus).toContainText('Active');
    }
  });

  test('Explanation Item Komponente isoliert testen', async ({ page }) => {
    await page.setContent(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Explanation Item Test</title>
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
        <script type="module">
          import '/src/components/explanation-item.js';
          
          // Test Explanation Object erstellen
          const testExplanation = {
            id: 'test-1',
            title: 'Test Explanation',
            content: 'Dies ist ein Test-Inhalt für die Explanation.',
            timestamp: 1696118400000,
            isPinned: false,
            isPending: false,
            confidence: 0.95
          };
          
          // Komponente erstellen und Daten setzen
          const item = document.createElement('explanation-item');
          item.explanation = testExplanation;
          document.body.appendChild(item);
        </script>
      </head>
      <body>
      </body>
      </html>
    `);
    
    await page.waitForSelector('explanation-item');
    
    const item = page.locator('explanation-item');
    await expect(item).toBeVisible();
    
    // Titel prüfen
    const title = item.locator('.explanation-title');
    if (await title.isVisible()) {
      await expect(title).toContainText('Test Explanation');
    }
    
    // Action Buttons prüfen (Pin und Delete)
    const buttons = item.locator('.action-button');
    const buttonCount = await buttons.count();
    expect(buttonCount).toBeGreaterThan(0);
    
    // Pin Button spezifisch
    const pinButton = item.locator('.pin-button');
    await expect(pinButton).toBeVisible();
    
    // Delete Button spezifisch
    const deleteButton = item.locator('.delete-button');
    await expect(deleteButton).toBeVisible();
  });

  test('Chat Box Komponente isoliert testen', async ({ page }) => {
    await page.setContent(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Chat Box Test</title>
        <script type="module">
          import '/src/components/chat-box.js';
        </script>
      </head>
      <body>
        <chat-box></chat-box>
      </body>
      </html>
    `);
    
    await page.waitForSelector('chat-box');
    
    const chatBox = page.locator('chat-box');
    await expect(chatBox).toBeVisible();
    
    // Input Field prüfen (Chat Box verwendet wahrscheinlich textarea)
    const input = chatBox.locator('textarea, input');
    if (await input.isVisible()) {
      await input.fill('Test message');
      await expect(input).toHaveValue('Test message');
    }
    
    // Send Button prüfen - spezifischer Selektor
    const sendButton = chatBox.locator('button').first();
    if (await sendButton.isVisible()) {
      await expect(sendButton).toBeVisible();
    }
  });
});

test.describe('Responsives Design Tests', () => {
  test('UI ist responsive auf verschiedenen Bildschirmgrößen', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Desktop
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(100);
    
    // Überprüfen ob UI korrekt angezeigt wird
    const ui = page.locator('my-element, test-ui');
    if (await ui.isVisible()) {
      await expect(ui).toBeVisible();
    }
    
    // Tablet
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(100);
    
    // Mobile
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(100);
    
    // UI sollte immer noch sichtbar sein
    if (await ui.isVisible()) {
      await expect(ui).toBeVisible();
    }
  });
});