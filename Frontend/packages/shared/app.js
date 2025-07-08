// frontend/packages/shared/app.js (FINALIZED with all CORRECTED PATHS for modules)

// All modules are now assumed to be under Frontend/packages/shared/src/
// or Frontend/packages/shared/src/modules/
import MessageQueue from './src/modules/MessageQueue.js'; // <--- PATH CORRECTED
import { WebSocketManager } from './src/modules/WebSocketManager.js'; // <--- PATH CORRECTED
console.log('app.js: WebSocketManager imported successfully. Type of WebSocketManager:', typeof WebSocketManager);

import { initializeEventListeners, setQueuesAndManager as setEventListenersQueuesAndManager } from './src/modules/EventListeners.js'; // <--- PATH CORRECTED
import { updateSystemLog } from './src/modules/QueueDisplay.js'; // <--- PATH CORRECTED
import { UniversalMessageParser } from './src/universal-message-parser.js'; // <--- PATH CORRECTED
import { explanationManager } from './src/explanation-manager.js'; // <--- PATH CORRECTED

// --- NEW: Generate a unique client ID for this session ---
const CLIENT_ID = 'client_' + Date.now().toString() + Math.random().toString(36).substring(2, 8);
console.log('Frontend Client ID:', CLIENT_ID);
// ---------------------------------------------------------

// Initialize Parser
window.UniversalMessageParser = UniversalMessageParser;

// Global Queue Instances - CREATED HERE AND ONLY HERE
// These are the frontend's specific queues for its internal message flow.
const frontendDisplayQueue = new MessageQueue('frontendDisplayQueue');
const frontendActionQueue = new MessageQueue('frontendActionQueue');
const toBackendQueue = new MessageQueue('toBackendQueue');
const fromBackendQueue = new MessageQueue('fromBackendQueue');

document.addEventListener('DOMContentLoaded', () => {
    // Add a guard to prevent multiple initializations from DOMContentLoaded
    if (document.body.dataset.initialized) {
        console.warn('app.js: DOMContentLoaded fired again, but already initialized. Skipping.');
        return;
    }
    document.body.dataset.initialized = 'true'; // Set flag to indicate initialization

    console.log('app.js: DOMContentLoaded (first time)');
    // Initialize the main application flow
    initializeApplication();
});

/**
 * Initializes the entire frontend application, including queues,
 * WebSocket communication, and event listeners.
 * @param {Object} [observer=null] - An optional observer object for WebSocket messages.
 */
export function initializeApplication(observer = null) {
    console.log('app.js: Initializing application...');
    updateSystemLog('Application starting initialization...');

    const webSocketManager = WebSocketManager; // Use the imported singleton instance directly
    console.log('app.js: webSocketManager variable assigned:', webSocketManager);

    // If an observer is provided (e.g., for global logging or specific message handling), set it.
    if (observer) {
        webSocketManager.setObserver(observer);
    }

    // Set the client ID in the WebSocketManager
    webSocketManager.setClientId(CLIENT_ID);

    // Centralize all queue instances into a single object for easy passing
    const queues = {
        frontendDisplayQueue,
        frontendActionQueue,
        toBackendQueue,
        fromBackendQueue
    };

    webSocketManager.setQueues(queues);
    console.log('app.js: Queues passed to WebSocketManager for internal management.');

    setEventListenersQueuesAndManager(queues, webSocketManager);
    console.log('app.js: Queues and WebSocketManager passed to EventListeners for UI interaction.');

    console.log('app.js: QueueDisplay module will be updated via WebSocketManager and MessageQueue subscriptions.');

    // Initialize core event listeners (e.g., button states, initial UI setup)
    initializeEventListeners();
    console.log('app.js: Event listeners initialized.');

    // Initiate the WebSocket connection.
    webSocketManager.connect();
    console.log('app.js: WebSocket connection initiated.');

    console.log('app.js: Queue display updates are now event-driven.');

    console.log('app.js: Application initialization complete.');
    updateSystemLog('Application initialized and ready.');
}