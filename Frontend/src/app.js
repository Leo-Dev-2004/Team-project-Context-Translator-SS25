// frontend/src/app.js

import { MessageQueue } from './modules/MessageQueue.js';
import { WebSocketManager } from './modules/WebSocketManager.js';
import { initializeEventListeners, processBackendMessages } from './modules/EventListeners.js';
import { updateAllQueueDisplays } from './modules/QueueDisplay.js';

// --- 1. Define Message Queues for inter-module communication and display ---
// These are the actual JavaScript MessageQueue instances living in your frontend.

// Messages representing actions or data originating from the frontend (frontend's local outbox)
export const frontendActionQueue = new MessageQueue('frontendAction'); // Renamed from fromFrontendQueue

// Messages leaving the frontend to the backend (frontend's outbound buffer to server)
export const toBackendQueue = new MessageQueue('toBackend'); // Name remains the same

// Messages arriving at the frontend from the backend (frontend's inbound buffer from server)
export const fromBackendQueue = new MessageQueue('fromBackend'); // Name remains the same

// Messages processed from backend, destined for specific frontend display/UI components (frontend's display inbox)
export const frontendDisplayQueue = new MessageQueue('frontendDisplay'); // Renamed from toFrontendQueue

// --- 2. Main Application Initialization ---

// Event listener for when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log("app.js: DOMContentLoaded");
    initialize();
});

// Asynchronous initialization function
async function initialize() {
    console.log("app.js: Initializing...");

    // 2.1 Set up WebSocketManager with the queues it needs
    // Pass the queues in the order WebSocketManager.setQueues expects:
    // (toBackend, fromBackend, frontendAction, frontendDisplay)
    //WebSocketManager.setQueues(toBackendQueue, fromBackendQueue, frontendActionQueue, frontendDisplayQueue);
    // NEW WAY (in app.js -> initialize function):
    WebSocketManager.setQueues({
        toBackendQueue: toBackendQueue,
        fromBackendQueue: fromBackendQueue,
        frontendActionQueue: frontendActionQueue,
        frontendDisplayQueue: frontendDisplayQueue
    });
    
    console.log("app.js: Queues passed to WebSocketManager.");

    // 2.2 Initialize all event listeners for UI interactions
    initializeEventListeners();
    console.log("app.js: Event listeners initialized.");

    // 2.3 Start the WebSocket connection
    WebSocketManager.connect();
    console.log("app.js: WebSocket connection initiated.");

    // 2.4 Start the continuous message processing loop for messages from the backend
    // This will run in the background, dequeuing messages from fromBackendQueue
    // and routing them to update functions or frontendDisplayQueue.
    processBackendMessages(); // This is an async function that runs indefinitely

    // 2.5 Start periodic UI updates for queue displays
    // requestAnimationFrame(updateAllQueueDisplays); // This will be called via setInterval/setTimeout in QueueDisplay
    updateAllQueueDisplays(); // Start the first update cycle immediately

    console.log("app.js: Initialization complete.");
}

// Any other global functions or exports (e.g., for direct debugging in console)
// (None defined explicitly in previous steps, but can be added if needed)