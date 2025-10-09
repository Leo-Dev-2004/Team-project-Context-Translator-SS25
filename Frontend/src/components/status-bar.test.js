// ## Test file for the StatusBar component
//    This file uses Mocha as the test framework and Chai for assertions.

// ------------------------------------------------------------------
// You have to install the following packages as dev dependencies:
// npm install @web/test-runner @open-wc/testing chai --save-dev
// ------------------------------------------------------------------


// Import testing helpers from the open-wc testing library
import { fixture, html } from '@open-wc/testing';
// Import the assertion library (chai in this case)
import { expect } from 'chai';

// Import the component you are testing
import './status-bar.js';

// 'describe' creates a test suite, a container for related tests.
describe('StatusBar Component', () => {

  // 'it' defines an individual test case.
  it('displays the server status "connected" correctly', async () => {
    // 1. Create the component in the test DOM using the 'fixture' helper.
    // We pass the 'serverStatus' property directly.
    const el = await fixture(html`<status-bar .serverStatus=${'connected'}></status-bar>`);

    // 2. Find the relevant elements within the component's Shadow DOM.
    const statusValue = el.shadowRoot.querySelector('.server .status-value');
    const indicator = el.shadowRoot.querySelector('.server .status-indicator');

    // 3. Assert the expected outcomes.
    // Check if the text content is correct.
    expect(statusValue.textContent).to.equal('connected');
    // Check if the indicator has the correct CSS class.
    expect(indicator.classList.contains('connected')).to.be.true;
    // Also, check that it doesn't have an incorrect class.
    expect(indicator.classList.contains('disconnected')).to.be.false;
  });

  it('displays the microphone status "muted" correctly', async () => {
    const el = await fixture(html`<status-bar .microphoneStatus=${'muted'}></status-bar>`);

    const statusValue = el.shadowRoot.querySelector('.microphone .status-value');
    const indicator = el.shadowRoot.querySelector('.microphone .status-indicator');

    expect(statusValue.textContent).to.equal('muted');
    expect(indicator.classList.contains('muted')).to.be.true;
  });

  it('renders with default initial statuses if no properties are provided', async () => {
    // Render the component without any properties.
    const el = await fixture(html`<status-bar></status-bar>`);

    const serverStatus = el.shadowRoot.querySelector('.server .status-value');
    const micStatus = el.shadowRoot.querySelector('.microphone .status-value');

    // The constructor sets default values, which should be reflected here.
    expect(serverStatus.textContent).to.equal('disconnected');
    expect(micStatus.textContent).to.equal('disconnected');
  });

  it('updates the server status when its property is changed', async () => {
    const el = await fixture(html`<status-bar .serverStatus=${'disconnected'}></status-bar>`);
    const statusValue = el.shadowRoot.querySelector('.server .status-value');
    const indicator = el.shadowRoot.querySelector('.server .status-indicator');

    // Verify initial state.
    expect(statusValue.textContent).to.equal('disconnected');
    expect(indicator.classList.contains('disconnected')).to.be.true;

    // Change the property on the element.
    el.serverStatus = 'trouble';
    // Wait for the component to re-render.
    await el.updateComplete;

    // Verify the new state.
    expect(statusValue.textContent).to.equal('trouble');
    expect(indicator.classList.contains('trouble')).to.be.true;
    expect(indicator.classList.contains('disconnected')).to.be.false;
  });
});