import { test, expect } from '@playwright/test';

test.describe('UI Component E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    
    // Navigate to Explanations tab
    await page.click('md-primary-tab:nth-child(2)');
    // Wait for tab content to load
    await page.waitForSelector('.explanations-panel');
  });



  // Test 1
  test('should add explanation on button click', async ({ page }) => {
    // Debug: Log the page content
    console.log(await page.content());
    
    // Wait for button and click
    const addTestButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
    await addTestButton.click();
    
    // Wait and check for explanation
    const explanation = await page.waitForSelector('explanation-item', { timeout: 15000 });
    expect(explanation).toBeTruthy();
  });


  test('should log all icon button names in explanation item after creation', async ({ page }) => {
  // Debug: Log the page content
    console.log(await page.content());

  // Add explanation
  const addTestButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
  await addTestButton.click();

  // explanation-item abwarten
  const explanationItem = page.locator('explanation-item').first();

  // Buttons im Shadow DOM suchen
 const buttons = page.locator('explanation-item >>> md-icon-button');
const buttonCount = await buttons.count();
console.log('Gefundene md-icon-buttons:', buttonCount);

for (let i = 0; i < buttonCount; i++) {
  const icon = buttons.nth(i).locator('md-icon');
  const text = await icon.textContent();
  console.log(`Button ${i + 1}:`, text && text.trim());
}

  // Sicherstellen, dass mindestens ein Button gefunden wurde
  expect(buttonCount).toBeGreaterThan(0);
});


test('should log all icon button names in explanation item after  2', async ({ page }) => {

  // 2. explanation-item abwarten
  console.log(await page.content());
    
    // Wait for button and click
    const addTestButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
    await addTestButton.click();
    
    // Wait and check for explanation
    const explanation = await page.waitForSelector('explanation-item', { timeout: 15000 });
    expect(explanation).toBeTruthy();

  // 3. Alle md-icon-buttons im explanation-item finden und alle Icon-Namen ausgeben
  const buttons = await explanation.$$('md-icon-button');
  for (const [i, btn] of buttons.entries()) {
    const icon = await btn.$('md-icon');
    const text = await icon.textContent();
    console.log(`Button ${i + 1}:`, text && text.trim());
  }

  // Optional: Prüfen, dass mindestens ein Button gefunden wurde
  expect(buttons.length).toBeGreaterThan(0);
});






  // Test 2
test('should remove explanation when delete clicked', async ({ page }) => {
  // 1. Add explanation
  const addTestButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
  await addTestButton.click();

  // 2. Wait for explanation-item to appear
  const explanationItem = await page.waitForSelector('explanation-item', { timeout: 15000 });

  const buttons = await explanationItem.$$('md-icon-button');
for (const btn of buttons) {
  const icon = await btn.$('md-icon');
  const text = await icon.textContent();
  console.log('Button icon:', text);
}

  // 3. Finde den Delete-Button im explanation-item
  // Falls explanation-item ein Shadow DOM host ist:
  let deleteButton;
  try {
    // Playwright kann standardmäßig nicht ins Shadow DOM von Custom Elements schauen.
    // Aber falls explanation-item KEIN Shadow DOM nutzt, reicht das:
    const deleteButton = await page.locator('explanation-item >>> md-icon-button:has(md-icon:text("delete"))').first();
  } catch {
    // Alternative: Versuche global im ersten explanation-item als Fallback
    deleteButton = await page.waitForSelector('explanation-item md-icon-button:has(md-icon:text("delete"))', { timeout: 5000 });
  }
  await deleteButton.click();

  // 4. explanation-item sollte entfernt sein
  await expect(page.locator('explanation-item')).toHaveCount(0);
});


  

  // Test 3
  test('should pin explanation', async ({ page }) => {
    console.log(await page.content());
    
    const button = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
    await button.click();
    
    const pinButton = await page.waitForSelector('explanation-item button.pin', { timeout: 15000 });
    await pinButton.click();
    
    await expect(page.locator('explanation-item[isPinned="true"]')).toHaveCount(1);
  });

  // Test 4
  test('should clear unpinned explanations but keep pinned ones', async ({ page }) => {
    console.log(await page.content());
    
    const addButton = await page.waitForSelector('md-filled-button:has-text("Add Test")', { timeout: 15000 });
    await addButton.click();
    await addButton.click();
    
    const pinButton = await page.waitForSelector('explanation-item >> nth=0 >> button.pin', { timeout: 15000 });
    await pinButton.click();
    
    const clearButton = await page.waitForSelector('md-text-button:has-text("Clear All")', { timeout: 15000 });
    await clearButton.click();
    
    await expect(page.locator('explanation-item')).toHaveCount(1);
    await expect(page.locator('explanation-item[isPinned="true"]')).toHaveCount(1);
  });

    
  // Test 5
  test('should save setup configuration', async ({ page }) => {
    // Navigate to Setup tab (it's the default, but let's be explicit)
    await page.click('md-primary-tab:nth-child(1)');
    
    // Fill in domain
    await page.fill('md-outlined-text-field', 'Software Developer');
    
    // Change language
    await page.click('md-outlined-select');
    await page.click('md-select-option[value="de"]');
    
    // Toggle auto-save
    await page.click('md-switch');
    
    // Save settings
    await page.click('md-filled-button:has-text("Save Configuration")');
    
    // Verify saved state (you might need to adapt this based on your implementation)
    await expect(page.locator('md-outlined-text-field')).toHaveValue('Software Developer');
    await expect(page.locator('md-outlined-select')).toHaveValue('de');
    await expect(page.locator('md-switch')).toBeChecked();
  });
});