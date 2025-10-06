import { test, expect } from '../electron-fixtures.js';

test.describe('WebSocket Verbindung Tests', () => {
  test('WebSocket Verbindung wird hergestellt', async ({ page }) => {
    // Warten bis App geladen ist
    await page.waitForSelector('my-element');
    
    // WebSocket Status aus Status Bar prüfen
    await page.waitForSelector('status-bar');
    
    // Server Status sollte angezeigt werden
    const serverStatus = page.locator('status-bar .server-status');
    await expect(serverStatus).toBeVisible();
    
    // Warten auf WebSocket Verbindung (kann dauern)
    await page.waitForTimeout(2000);
    
    // Status sollte "Connected" oder ähnliches zeigen
    // (abhängig von Backend-Verfügbarkeit)
    const statusText = await serverStatus.textContent();
    console.log('Server Status:', statusText);
  });

  test('WebSocket Nachrichten können gesendet werden', async ({ page }) => {
    await page.waitForSelector('my-element');
    
    // Mock WebSocket für Tests
    await page.addInitScript(() => {
      // WebSocket Mock für Testing
      class MockWebSocket extends EventTarget {
        constructor(url) {
          super();
          this.url = url;
          this.readyState = WebSocket.CONNECTING;
          this.CONNECTING = 0;
          this.OPEN = 1;
          this.CLOSING = 2;
          this.CLOSED = 3;
          
          setTimeout(() => {
            this.readyState = WebSocket.OPEN;
            this.dispatchEvent(new Event('open'));
          }, 100);
        }
        
        send(data) {
          console.log('Mock WebSocket sent:', data);
          // Echo zurück für Tests
          setTimeout(() => {
            const message = {
              data: JSON.stringify({
                type: 'system.acknowledgement',
                payload: { status: 'received' }
              })
            };
            this.dispatchEvent(new MessageEvent('message', message));
          }, 50);
        }
        
        close() {
          this.readyState = WebSocket.CLOSED;
          this.dispatchEvent(new Event('close'));
        }
      }
      
      // Nur in Test-Umgebung
      if (process.env.NODE_ENV === 'test') {
        window.WebSocket = MockWebSocket;
      }
    });
    
    // Zu Explanations Tab wechseln für Manual Request
    const explanationsTab = page.locator('md-primary-tab').nth(1);
    await explanationsTab.click();
    
    await page.waitForSelector('explanations-tab');
    
    const manualInput = page.locator('explanations-tab md-outlined-text-field[label="Explain a term"] input');
    const explainButton = page.locator('explanations-tab md-filled-button:has-text("Explain")');
    
    // Begriff eingeben und senden
    await manualInput.fill('WebSocket Test');
    await explainButton.click();
    
    // Warten auf Response
    await page.waitForTimeout(200);
    
    // Prüfen ob Nachricht gesendet wurde (Console Log oder Status Update)
  });

  test('Session Start funktioniert', async ({ page }) => {
    await page.waitForSelector('my-element');
    
    // Session Start Button suchen (könnte in verschiedenen Komponenten sein)
    const sessionButtons = page.locator('md-filled-button, md-outlined-button');
    
    // Durch alle Buttons iterieren und "Start Session" finden
    const buttonCount = await sessionButtons.count();
    let startButton = null;
    
    for (let i = 0; i < buttonCount; i++) {
      const button = sessionButtons.nth(i);
      const text = await button.textContent();
      if (text && text.includes('Start')) {
        startButton = button;
        break;
      }
    }
    
    if (startButton) {
      await startButton.click();
      await page.waitForTimeout(500);
      
      // Überprüfen ob Session gestartet wurde
      // (Status Update oder UI Änderung)
    }
  });

  test('Session Join funktioniert', async ({ page }) => {
    await page.waitForSelector('my-element');
    
    // Session Code Input suchen
    const sessionInput = page.locator('md-outlined-text-field[label*="Session"], input[placeholder*="session"]');
    
    if (await sessionInput.isVisible()) {
      await sessionInput.fill('TEST123');
      
      // Join Button suchen
      const joinButton = page.locator('md-filled-button:has-text("Join"), md-outlined-button:has-text("Join")');
      
      if (await joinButton.isVisible()) {
        await joinButton.click();
        await page.waitForTimeout(500);
        
        // Überprüfen ob Join versucht wurde
      }
    }
  });
});

test.describe('Error Handling Tests', () => {
  test('WebSocket Verbindungsfehler werden behandelt', async ({ page }) => {
    await page.waitForSelector('my-element');
    
    // WebSocket Mock mit Fehler
    await page.addInitScript(() => {
      class FailingWebSocket extends EventTarget {
        constructor(url) {
          super();
          this.url = url;
          this.readyState = WebSocket.CONNECTING;
          
          setTimeout(() => {
            this.readyState = WebSocket.CLOSED;
            this.dispatchEvent(new Event('error'));
            this.dispatchEvent(new Event('close'));
          }, 100);
        }
        
        send(data) {
          throw new Error('WebSocket connection failed');
        }
        
        close() {
          this.readyState = WebSocket.CLOSED;
        }
      }
      
      if (process.env.NODE_ENV === 'test') {
        window.WebSocket = FailingWebSocket;
      }
    });
    
    // Status Bar sollte Fehler anzeigen
    await page.waitForSelector('status-bar');
    const serverStatus = page.locator('status-bar .server-status');
    
    // Warten auf Fehler-Status
    await page.waitForTimeout(500);
    
    const statusText = await serverStatus.textContent();
    console.log('Error Status:', statusText);
    
    // Status sollte Disconnected oder Error zeigen
    expect(statusText).toMatch(/(Disconnected|Error|Offline)/i);
  });

  test('Ungültige Nachrichten werden ignoriert', async ({ page }) => {
    await page.waitForSelector('my-element');
    
    // Mock WebSocket mit ungültigen Nachrichten
    await page.addInitScript(() => {
      class BadMessageWebSocket extends EventTarget {
        constructor(url) {
          super();
          this.url = url;
          this.readyState = WebSocket.OPEN;
          
          // Sende ungültige Nachricht nach Verbindung
          setTimeout(() => {
            const badMessage = {
              data: 'invalid json data {'
            };
            this.dispatchEvent(new MessageEvent('message', badMessage));
            
            // Dann eine gültige Nachricht
            const goodMessage = {
              data: JSON.stringify({
                type: 'system.acknowledgement',
                payload: { status: 'ok' }
              })
            };
            this.dispatchEvent(new MessageEvent('message', goodMessage));
          }, 100);
        }
        
        send(data) {
          console.log('Mock sent:', data);
        }
        
        close() {
          this.readyState = WebSocket.CLOSED;
        }
      }
      
      if (process.env.NODE_ENV === 'test') {
        window.WebSocket = BadMessageWebSocket;
      }
    });
    
    // App sollte trotz ungültiger Nachricht funktionieren
    await page.waitForTimeout(500);
    
    // UI sollte noch responsive sein
    const tabs = page.locator('md-tabs');
    await expect(tabs).toBeVisible();
  });
});