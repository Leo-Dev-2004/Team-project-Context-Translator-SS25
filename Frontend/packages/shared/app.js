// frontend/packages/shared/app.js

import MessageQueue from './src/modules/MessageQueue.js';
import { WebSocketManager } from './src/modules/WebSocketManager.js';
import { initializeEventListeners, setQueuesAndManager as setEventListenersQueuesAndManager } from './src/modules/EventListeners.js';
import { updateSystemLog } from './src/modules/QueueDisplay.js';
import { UniversalMessageParser } from './src/universal-message-parser.js'; // Corrected path
import { explanationManager } from './src/explanation-manager.js'; // Corrected path

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

// REMOVE THIS DOMContentLoaded LISTENER FROM APP.JS
// document.addEventListener('DOMContentLoaded', () => {
//     if (document.body.dataset.initialized) {
//         console.warn('app.js: DOMContentLoaded fired again, but already initialized. Skipping.');
//         return;
//     }
//     document.body.dataset.initialized = 'true';
//     console.log('app.js: DOMContentLoaded (first time)');
//     initializeApplication(); // This call will now be removed
// });

/**
 * Initializes the entire frontend application, including queues,
 * WebSocket communication, and event listeners.
 * This function should be called ONCE, and passed the main UI component instance.
 * @param {Object} uiComponent - The instance of the main UI component (ElectronMyElement).
 */
export function initializeApplication(uiComponent) { // uiComponent is now REQUIRED
    console.log('app.js: Initializing application with UI component...');
    updateSystemLog('Application starting initialization...');

    const webSocketManager = WebSocketManager;

    // Set the UI component reference in the WebSocketManager FIRST.
    // This is crucial for WebSocketManager to find UI elements in the shadow DOM.
    if (!uiComponent) {
        console.error('app.js: initializeApplication called without a UI component instance. Cannot proceed with UI updates.');
        updateSystemLog('Application initialization failed: UI component missing.');
        return; // Halt initialization if UI component is not provided
    }
    webSocketManager.setUIComponent(uiComponent);
    console.log('app.js: UI component instance set in WebSocketManager.');


    webSocketManager.setClientId(CLIENT_ID);

    const queues = {
        frontendDisplayQueue,
        frontendActionQueue,
        toBackendQueue,
        fromBackendQueue
    };

    webSocketManager.setQueues(queues);

    // Pass uiComponent to EventListeners as well, if it needs to access shadow DOM elements
    setEventListenersQueuesAndManager(queues, webSocketManager, uiComponent);

    initializeEventListeners(); // This might need to be adjusted if it relies on uiComponent directly

    webSocketManager.connect();
    console.log('app.js: WebSocket connection initiated.');

    console.log('app.js: Application initialization complete.');
    updateSystemLog('Application initialized and ready.');
}
