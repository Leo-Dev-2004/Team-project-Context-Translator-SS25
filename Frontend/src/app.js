// frontend/src/app.js

import MessageQueue from './modules/MessageQueue.js'; // This now works with the default export
import { WebSocketManager } from './modules/WebSocketManager.js';
import { initializeEventListeners, setQueuesAndManager as setEventListenersQueuesAndManager } from './modules/EventListeners.js';
import { updateAllQueueDisplays, updateSystemLog, setQueues as setQueueDisplayQueues } from './modules/QueueDisplay.js';


// Global Queue Instances - CREATED HERE AND ONLY HERE
const frontendDisplayQueue = new MessageQueue('frontendDisplayQueue');
const frontendActionQueue = new MessageQueue('frontendActionQueue');
const toBackendQueue = new MessageQueue('toBackendQueue');
const fromBackendQueue = new MessageQueue('fromBackendQueue');

// No need to export individual queues from app.js now, as they are passed by reference.
// If another module needs direct access for some reason without a setter, you could export,
// but passing via setters is generally preferred for clarity.

document.addEventListener('DOMContentLoaded', () => {
    console.log('app.js: DOMContentLoaded');
    initializeApplication();
});

export function initializeApplication(observer = null) {
    console.log('app.js: Initializing...');

    // Get WebSocketManager instance
    const webSocketManager = WebSocketManager;

    // Set observer if provided
    if (observer) {
        webSocketManager.setObserver(observer);
    }

    // Initialize queues
    const queues = {
        frontendDisplayQueue,
        frontendActionQueue,
        toBackendQueue,
        fromBackendQueue
    };

    // Pass queues to WebSocketManager
    webSocketManager.setQueues(queues);
    console.log('app.js: Queues passed to WebSocketManager.');

    // Pass queues and WebSocketManager to EventListeners module
    setEventListenersQueuesAndManager(queues, webSocketManager);
    console.log('app.js: Queues and WebSocketManager passed to EventListeners.');

    // Pass queues to QueueDisplay module
    setQueueDisplayQueues(queues);
    console.log('app.js: Queues passed to QueueDisplay.');


    // Initialize event listeners (buttons, custom events etc.)
    initializeEventListeners();
    console.log('app.js: Event listeners initialized.');

    // Connect to WebSocket
    webSocketManager.connect();
    console.log('app.js: WebSocket connection initiated.');

    // Initial display update
    updateAllQueueDisplays();

    console.log('app.js: Initialization complete.');
    updateSystemLog('Application initialized successfully.');
}
