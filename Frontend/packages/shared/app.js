// frontend/src/app.js

import MessageQueue from './modules/MessageQueue.js';
import { WebSocketManager } from './modules/WebSocketManager.js'; // Imports the singleton instance
import { initializeEventListeners, setQueuesAndManager as setEventListenersQueuesAndManager } from './modules/EventListeners.js';
import { updateSystemLog } from './modules/QueueDisplay.js'; // Only import necessary logging functions
import { UniversalMessageParser } from './universal-message-parser.js';
import { explanationManager } from './explanation-manager.js';

// --- NEW: Generate a unique client ID for this session ---
const CLIENT_ID = 'client_' + Date.now().toString() + Math.random().toString(36).substring(2, 8);
console.log('Frontend Client ID:', CLIENT_ID);
// ---------------------------------------------------------

// Initialize Parser
window.UniversalMessageParser = UniversalMessageParser;

// Global Queue Instances - CREATED HERE AND ONLY HERE
// These are the frontend's specific queues for its internal message flow.
const frontendDisplayQueue = new MessageQueue('frontendDisplayQueue'); // Messages processed for frontend display (e.g., UI updates)
const frontendActionQueue = new MessageQueue('frontendActionQueue'); // Messages representing actions initiated by the frontend
const toBackendQueue = new MessageQueue('toBackendQueue');           // Messages explicitly destined TO the backend
const fromBackendQueue = new MessageQueue('fromBackendQueue');         // Messages explicitly received FROM the backend

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

    // If an observer is provided (e.g., for global logging or specific message handling), set it.
    if (observer) {
        webSocketManager.setObserver(observer);
    }

    // Set the client ID in the WebSocketManager
    webSocketManager.setClientId(CLIENT_ID); // <-- Set the generated client ID

    // Centralize all queue instances into a single object for easy passing
    const queues = {
        frontendDisplayQueue,
        frontendActionQueue,
        toBackendQueue,
        fromBackendQueue
    };

    // Pass queue instances to WebSocketManager.
    // WebSocketManager will handle:
    // 1. Enqueuing outgoing messages to `toBackendQueue` before sending.
    // 2. Enqueuing incoming messages to `fromBackendQueue` for processing.
    // 3. Subscribing to `toBackendQueue` and `fromBackendQueue` for their own UI display updates.
    // 4. Handling backend queue status updates (`queue_status_update` type) and updating `QueueDisplay` directly.
    webSocketManager.setQueues(queues);
    //console.log('app.js: Queues passed to WebSocketManager for internal management.');

    // Pass queues and WebSocketManager to EventListeners module.
    // EventListeners will:
    // 1. Set up UI event handlers (button clicks, form submissions).
    // 2. Potentially dequeue from `fromBackendQueue` for processing.
    // 3. Enqueue to `toBackendQueue` when sending user-initiated actions.
    setEventListenersQueuesAndManager(queues, webSocketManager);
    //console.log('app.js: Queues and WebSocketManager passed to EventListeners for UI interaction.');

    // No need to pass queues to QueueDisplay directly here via `setQueueDisplayQueues`.
    // The `QueueDisplay` module's `updateQueueDisplay` function is now designed to be called
    // by `WebSocketManager` for backend queue updates and by the `MessageQueue` instances
    // themselves (via their `subscribe` method, which is set up in `WebSocketManager.setQueues`).
    //console.log('app.js: QueueDisplay module will be updated via WebSocketManager and MessageQueue subscriptions.');


    // Initialize core event listeners (e.g., button states, initial UI setup)
    initializeEventListeners();
    //console.log('app.js: Event listeners initialized.');

    // Initiate the WebSocket connection.
    // The webSocketManager.connect() method will now internally use the CLIENT_ID
    // that was set via `setClientId`. The default URL in `connect` is fine.
    webSocketManager.connect(); // No need to pass the URL here, as it's handled internally.
    console.log('app.js: WebSocket connection initiated.');

    // No need for `requestAnimationFrame(updateAllQueueDisplays)` here.
    // QueueDisplay updates are now event-driven:
    // - Frontend queue changes trigger `MessageQueue`'s `notifyListeners` (which calls `updateQueueDisplay`).
    // - Backend queue status messages are handled directly by `WebSocketManager` which calls `updateQueueDisplay`.
    //console.log('app.js: Queue display updates are now event-driven.');

    console.log('app.js: Application initialization complete.');
    updateSystemLog('Application initialized and ready.');
}