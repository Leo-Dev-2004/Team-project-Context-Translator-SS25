# Frontend Tests mit Playwright

Dieses Verzeichnis enthält End-to-End und Komponenten-Tests für das Context Translator Frontend.

## 🏗️ **Test-Struktur**

```
tests/
├── electron/                    # Electron App E2E Tests
│   ├── ui-basic.spec.js        # Grundlegende UI Tests
│   ├── explanation-manager.spec.js  # Explanation Management
│   └── websocket.spec.js       # WebSocket Integration
├── components/                  # Isolierte Komponenten Tests
│   └── isolated.spec.js        # Komponenten ohne Electron
├── electron-fixtures.js        # Electron Test Utilities
└── README.md                   # Diese Datei
```

## 🚀 **Tests ausführen**

### Alle Tests
```bash
npm test
```

### Nur Electron Tests
```bash
npm run test:electron
```

### Nur Komponenten Tests
```bash
npm run test:components
```

### Tests mit Browserfenster (headed)
```bash
npm run test:headed
```

### Debug Modus
```bash
npm run test:debug
```

### Spezifische Tests
```bash
# Nur UI Tests
npm run test:ui

# Spezifische Datei
npx playwright test ui-basic.spec.js

# Spezifischer Test
npx playwright test --grep "Tab-Navigation"
```

## 🔧 **Setup**

### Erstmalige Installation
```bash
# Playwright installieren
npm install

# Playwright Browser installieren
npm run test:install
```

### Vor Tests
```bash
# Preload Script builden (für Electron Tests)
npm run build:preload

# Vite Dev Server starten (für Komponenten Tests)
npm run dev:renderer
```

## 📋 **Test-Kategorien**

### 1. **UI Grundfunktionen** (`ui-basic.spec.js`)
- ✅ App Startup
- ✅ Tab Navigation (Setup ↔ Explanations)
- ✅ Input Felder (Domain, Manual Request)
- ✅ Buttons und Interaktionen
- ✅ Status Bar Anzeige

### 2. **Explanation Manager** (`explanation-manager.spec.js`)
- ✅ Explanations hinzufügen/entfernen
- ✅ Expand/Collapse Funktionalität
- ✅ Pin/Unpin Erklärungen  
- ✅ Dark Mode Toggle
- ✅ Leere Liste Handling

### 3. **WebSocket Integration** (`websocket.spec.js`)
- ✅ Verbindungsaufbau
- ✅ Nachrichten senden/empfangen
- ✅ Session Start/Join
- ✅ Error Handling
- ✅ Reconnection Logic

### 4. **Isolierte Komponenten** (`isolated.spec.js`)
- ✅ Komponenten ohne Electron Context
- ✅ Status Bar isoliert
- ✅ Explanation Item isoliert
- ✅ Chat Box isoliert
- ✅ Responsive Design
- ✅ Accessibility

## 🎯 **Test-Features**

### **Electron App Tests**
- Starten echte Electron App
- Testen vollständige User Journey
- WebSocket Mocking für Backend-lose Tests
- Screenshot bei Fehlern

### **Komponenten Tests**
- Testen einzelne Lit Components
- Ohne Electron Overhead
- Schneller für Unit-Test-ähnliche Szenarien
- Vite Dev Server Integration

### **Mocking & Stubs**
- WebSocket Mock für offline Tests
- Error Simulation
- Backend Response Simulation

## 🔍 **Debug & Troubleshooting**

### Tests debuggen
```bash
# Mit Browser öffnen
npm run test:debug

# Spezifischen Test debuggen
npx playwright test --debug ui-basic.spec.js
```

### Screenshots & Videos
```bash
# Tests mit Screenshots
npx playwright test --screenshot=only-on-failure

# Test Report anzeigen
npx playwright show-report
```

### Häufige Probleme

**1. Electron startet nicht**
```bash
# Preload Script muss gebaut sein
npm run build:preload
```

**2. WebSocket Tests fehlschlagen**
- Backend nicht erreichbar → Tests nutzen Mocks
- Ports blockiert → Andere Terminals schließen

**3. Komponenten Tests fehlschlagen**
```bash
# Vite Dev Server muss laufen
npm run dev:renderer
```

**4. Timing Issues**
- `page.waitForSelector()` nutzen
- `page.waitForTimeout()` sparsam verwenden
- `page.waitForLoadState()` für Seitenladung

## 📊 **Test Reports**

### HTML Report
```bash
# Report generieren und öffnen
npx playwright show-report
```

### CI/CD Integration
- GitHub Actions Workflow in `.github/workflows/playwright.yml`
- Automatische Tests bei Push/PR
- Test Reports als Artifacts

## 💡 **Best Practices**

### **Test-Struktur**
```javascript
test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    // Setup für alle Tests in dieser Gruppe
  });

  test('sollte spezifisches Verhalten testen', async ({ page }) => {
    // Arrange
    await page.waitForSelector('my-element');
    
    // Act
    await page.click('button');
    
    // Assert
    await expect(page.locator('.result')).toBeVisible();
  });
});
```

### **Selektoren**
```javascript
// ✅ Gute Selektoren
page.locator('md-filled-button:has-text("Save")')
page.locator('[data-testid="explanation-item"]')
page.locator('setup-tab md-outlined-text-field[label="Domain"]')

// ❌ Vermeiden
page.locator('.btn-primary')  // CSS Klassen können sich ändern
page.locator('div > div > button')  // Fragile DOM Struktur
```

### **Warten & Timing**
```javascript
// ✅ Explicit Waits
await page.waitForSelector('my-element');
await page.waitForLoadState('networkidle');

// ❌ Vermeiden
await page.waitForTimeout(3000);  // Feste Wartezeiten
```

## 🧪 **Neue Tests hinzufügen**

### Electron Test
```javascript
// tests/electron/new-feature.spec.js
import { test, expect } from '../electron-fixtures.js';

test.describe('Neue Feature', () => {
  test('sollte Feature X testen', async ({ page }) => {
    // Test Implementation
  });
});
```

### Komponenten Test
```javascript
// tests/components/new-component.spec.js
import { test, expect } from '@playwright/test';

test.describe('Neue Komponente', () => {
  test('sollte isoliert funktionieren', async ({ page }) => {
    await page.setContent(`
      <!DOCTYPE html>
      <html>
        <head>
          <script type="module">
            import '/src/components/new-component.js';
          </script>
        </head>
        <body>
          <new-component></new-component>
        </body>
      </html>
    `);
    
    // Test Implementation
  });
});
```