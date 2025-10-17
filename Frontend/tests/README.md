# Frontend Tests with Playwright

This directory contains End-to-End and component tests for the Context Translator Frontend.

## 🏗️ **Test Structure**

```
tests/
├── electron/                        # Electron App E2E Tests
│   ├── ui-basic.spec.js             # Basic UI Tests
│   ├── explanation-manager.spec.js  # Explanation Management
│   └── websocket.spec.js            # WebSocket Integration
├── components/                      # Isolated Component Tests
│   └── isolated.spec.js             # Components without Electron
├── electron-fixtures.js             # Electron Test Utilities
└── README.md                        # This file
```

## 🚀 **Running Tests**
```bash
cd Frontend
```

### All Tests
```bash
npm test
```

### Electron Tests Only
```bash
npm run test:electron
```

### Component Tests Only
```bash
npm run test:components
```

### Tests with Browser Window (headed)
```bash
npm run test:headed
```

### Specific Tests
```bash
# UI Tests only
npm run test:ui

# Specific file
npx playwright test ui-basic.spec.js

# Specific test
npx playwright test --grep "Tab-Navigation"
```

## 🔧 **Setup**

### Initial Installation
```bash
# Install Playwright
npm install

# Install Playwright browsers
npm run test:install
```

### Before Tests
```bash
# Build preload script (for Electron tests)
npm run build:preload

# Start Vite dev server (for component tests)
npm run dev:renderer
```

## 📋 **Test Categories**

### 1. **Basic UI Functions** (`ui-basic.spec.js`)
- ✅ App Startup
- ✅ Tab Navigation (Setup ↔ Explanations)
- ✅ Input Fields (Domain, Manual Request)
- ✅ Buttons and Interactions
- ✅ Status Bar Display

### 2. **Explanation Manager** (`explanation-manager.spec.js`)
- ✅ Add/Remove Explanations
- ✅ Expand/Collapse Functionality
- ✅ Pin/Unpin Explanations  
- ✅ Dark Mode Toggle
- ✅ Empty List Handling

### 3. **WebSocket Integration** (`websocket.spec.js`)
- ✅ Connection Establishment
- ✅ Send/Receive Messages
- ✅ Session Start/Join
- ✅ Error Handling
- ✅ Reconnection Logic

### 4. **Isolated Components** (`isolated.spec.js`)
- ✅ Components without Electron Context
- ✅ Status Bar isolated
- ✅ Explanation Item isolated
- ✅ Chat Box isolated
- ✅ Responsive Design
- ✅ Accessibility

## 🎯 **Test Features**

### **Electron App Tests**
- Launch real Electron App
- Test complete user journey
- WebSocket mocking for backend-less tests
- Screenshots on failures

### **Component Tests**
- Test individual Lit Components
- Without Electron overhead
- Faster for unit-test-like scenarios
- Vite dev server integration

### **Mocking & Stubs**
- WebSocket mock for offline tests
- Error simulation
- Backend response simulation

## 🔍 **Debug & Troubleshooting**

### Debug Tests
```bash
# Open with browser
npm run test:debug

# Debug specific test
npx playwright test --debug ui-basic.spec.js
```

### Screenshots & Videos
```bash
# Tests with screenshots
npx playwright test --screenshot=only-on-failure

# Show test report
npx playwright show-report
```

### Common Issues

**1. Electron won't start**
```bash
# Preload script must be built
npm run build:preload
```

**2. WebSocket tests fail**
- Backend unreachable → Tests use mocks
- Ports blocked → Close other terminals

**3. Component tests fail**
```bash
# Vite dev server must be running
npm run dev:renderer
```

**4. Timing Issues**
- Use `page.waitForSelector()`
- Use `page.waitForTimeout()` sparingly
- Use `page.waitForLoadState()` for page loading

## 📊 **Test Reports**

### HTML Report
```bash
# Generate and open report
npx playwright show-report
```

### CI/CD Integration
- GitHub Actions workflow in `.github/workflows/playwright.yml`
- Automatic tests on Push/PR
- Test reports as artifacts

## 💡 **Best Practices**

### **Test Structure**
```javascript
test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    // Setup for all tests in this group
  });

  test('should test specific behavior', async ({ page }) => {
    // Arrange
    await page.waitForSelector('my-element');
    
    // Act
    await page.click('button');
    
    // Assert
    await expect(page.locator('.result')).toBeVisible();
  });
});
```
