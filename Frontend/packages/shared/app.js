// frontend/packages/shared/app.js (MODIFIED to accept and pass UI component instance)

import MessageQueue from './src/modules/MessageQueue.js';
import { WebSocketManager } from './src/modules/WebSocketManager.js';
console.log('app.js: WebSocketManager imported successfully. Type of WebSocketManager:', typeof WebSocketManager);

import { initializeEventListeners, setQueuesAndManager as setEventListenersQueuesAndManager } from './src/modules/EventListeners.js';
import { updateSystemLog, setUIDomElements as setQueueDisplayUIDomElements } from './src/modules/QueueDisplay.js'; // <-- MODIFIED IMPORT
import { UniversalMessageParser } from './src/universal-message-parser.js';
import { explanationManager } from './src/explanation-manager.js';

// --- NEW: Generate a unique client ID for this session ---
const CLIENT_ID = 'client_' + Date.now().toString() + Math.random().toString(36).substring(2, 8);
console.log('Frontend Client ID:', CLIENT_ID);
// ---------------------------------------------------------

// Initialize Parser
window.UniversalMessageParser = UniversalMessageParser;

// Global Queue Instances - CREATED HERE AND ONLY HERE
const frontendDisplayQueue = new MessageQueue('frontendDisplayQueue');
const frontendActionQueue = new MessageQueue('frontendActionQueue');
const toBackendQueue = new MessageQueue('toBackendQueue');
const fromBackendQueue = new MessageQueue('fromBackendQueue');

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.initialized) {
        console.warn('app.js: DOMContentLoaded fired again, but already initialized. Skipping.');
        return;
    }
    document.body.dataset.initialized = 'true';

    console.log('app.js: DOMContentLoaded (first time)');
    // initializeApplication will now be called from renderer.js's connectedCallback
    // so this DOMContentLoaded listener might become redundant or just for initial setup.
    // We will keep it for now for robustness.
});

/**
 * Initializes the entire frontend application, including queues,
 * WebSocket communication, and event listeners.
 * @param {Object} uiComponent - The instance of the main UI component (ElectronMyElement).
 */
export function initializeApplication(uiComponent) { // <--- MODIFIED: Accepts uiComponent
    if (!uiComponent || typeof uiComponent.shadowRoot === 'undefined') {
        console.error('app.js: initializeApplication called without a valid UI component instance.');
        return;
    }

    console.log('app.js: Initializing application with UI component...');
    updateSystemLog('Application starting initialization...');

    // Pass the UI component's shadowRoot (or the component itself if elements are in light DOM)
    // to modules that need to query DOM elements.
    setQueueDisplayUIDomElements(uiComponent); // <--- NEW: Pass UI component to QueueDisplay
    WebSocketManager.setUIComponent(uiComponent); // <--- NEW: Pass UI component to WebSocketManager

    const webSocketManager = WebSocketManager;
    console.log('app.js: webSocketManager variable assigned:', webSocketManager);

    webSocketManager.setClientId(CLIENT_ID);

    const queues = {
        frontendDisplayQueue,
        frontendActionQueue,
        toBackendQueue,
        fromBackendQueue
    };

    webSocketManager.setQueues(queues);
    console.log('app.js: Queues passed to WebSocketManager for internal management.');

    setEventListenersQueuesAndManager(queues, webSocketManager, uiComponent); // <--- MODIFIED: Pass uiComponent
    console.log('app.js: Queues and WebSocketManager passed to EventListeners for UI interaction.');

    console.log('app.js: QueueDisplay module will be updated via WebSocketManager and MessageQueue subscriptions.');

    initializeEventListeners();
    console.log('app.js: Event listeners initialized.');

    webSocketManager.connect();
    console.log('app.js: WebSocket connection initiated.');

    console.log('app.js: Queue display updates are now event-driven.');

    console.log('app.js: Application initialization complete.');
    updateSystemLog('Application initialized and ready.');
}