import { test, expect } from '@playwright/test';

test.describe('Frontend E2E Tests (vereinfacht)', () => {
  test.beforeEach(async ({ page }) => {
    // Navigiere zu Vite Dev Server 
    await page.goto('http://localhost:5174');
    await page.waitForLoadState('networkidle');
  });

  test('Frontend Seite lädt korrekt', async ({ page }) => {
    // Überprüfen ob Context Translator Seite geladen wird
    await expect(page).toHaveTitle(/Context Translator/);
    
    // Body sollte sichtbar sein
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('Module können geladen werden', async ({ page }) => {
    // Test ob Module korrekt importiert werden können
    const result = await page.evaluate(async () => {
      try {
        // Teste Import der UI Komponente
        const module = await import('/src/components/ui.js');
        return { success: true, hasUI: !!module.UI };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.hasUI).toBe(true);
    }
  });

  test('Explanation Item kann dynamisch erstellt werden', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        // Import und Komponente erstellen
        const { ExplanationItem } = await import('/src/components/explanation-item.js');
        
        if (!customElements.get('explanation-item')) {
          customElements.define('explanation-item', ExplanationItem);
        }
        
        const item = document.createElement('explanation-item');
        item.explanation = {
          id: 'test-1',
          title: 'Dynamic Test',
          content: 'Dynamisch erstellte Explanation',
          timestamp: Date.now(),
          isPinned: false
        };
        
        document.body.appendChild(item);
        
        // Warten auf Render
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Warten bis Shadow DOM gerendert ist
        await new Promise(resolve => setTimeout(resolve, 500));
        
        const element = document.querySelector('explanation-item');
        let hasTitle = false;
        
        if (element && element.shadowRoot) {
          const titleElement = element.shadowRoot.querySelector('.explanation-title');
          hasTitle = titleElement?.textContent?.includes('Dynamic Test') || false;
        }
        
        return { 
          success: true, 
          hasElement: !!element,
          hasTitle: hasTitle
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.hasElement).toBe(true);
      expect(result.hasTitle).toBe(true);
    }
  });

  test('Status Bar kann erstellt werden', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        await import('/src/components/status-bar.js');
        
        const statusBar = document.createElement('status-bar');
        statusBar.setAttribute('server-status', 'Connected');
        statusBar.setAttribute('microphone-status', 'Active');
        
        document.body.appendChild(statusBar);
        
        await new Promise(resolve => setTimeout(resolve, 100));
        
        return { 
          success: true, 
          hasElement: !!document.querySelector('status-bar')
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.hasElement).toBe(true);
    }
  });
});

test.describe('Komponenten Integration Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5174');
    await page.waitForLoadState('networkidle');
  });

  test('Alle Komponenten können importiert werden', async ({ page }) => {
    const components = [
      '/src/components/ui.js',
      '/src/components/explanation-item.js', 
      '/src/components/status-bar.js',
      '/src/components/chat-box.js',
      '/src/components/explanation-manager.js',
      '/src/components/setup-tab.js',
      '/src/components/explanations-tab.js',
      '/src/components/main-body.js'
    ];
    
    for (const component of components) {
      const result = await page.evaluate(async (componentPath) => {
        try {
          await import(componentPath);
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message, component: componentPath };
        }
      }, component);
      
      expect(result.success).toBe(true);
    }
  });

  test('Erstellung mehrerer Explanation Items', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        const { ExplanationItem } = await import('/src/components/explanation-item.js');
        
        if (!customElements.get('explanation-item')) {
          customElements.define('explanation-item', ExplanationItem);
        }
        
        // Mehrere Items erstellen
        const items = [];
        for (let i = 0; i < 3; i++) {
          const item = document.createElement('explanation-item');
          item.explanation = {
            id: `test-${i}`,
            title: `Test Item ${i}`,
            content: `Content für Item ${i}`,
            timestamp: Date.now() + i,
            isPinned: i === 1
          };
          
          document.body.appendChild(item);
          items.push(item);
        }
        
        await new Promise(resolve => setTimeout(resolve, 200));
        
        const itemElements = document.querySelectorAll('explanation-item');
        
        return { 
          success: true, 
          itemCount: itemElements.length,
          hasItems: itemElements.length === 3
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.itemCount).toBe(3);
    }
  });

  test('Styles werden korrekt geladen', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        await import('/src/components/styles.js');
        return { success: true };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    expect(result.success).toBe(true);
  });
});