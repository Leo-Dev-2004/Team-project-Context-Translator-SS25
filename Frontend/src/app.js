// Haupt-Einstiegspunkt der Anwendung
import { WebSocketManager } from './modules/WebSocketManager.js';
import { processBackendMessages } from './modules/EventListeners.js';
import { MessageQueue } from './modules/MessageQueue.js'; // This is the class
import { initializeEventListeners } from './modules/EventListeners.js'; // This is the function
// We don't need to import SimulationManager or QueueDisplay here,
// as their functions are used/imported by EventListeners.js directly.

// Message Queues for inter-module communication
export const toFrontendQueue = new MessageQueue('toFrontend');
export const fromFrontendQueue = new MessageQueue('fromFrontend'); 
export const toBackendQueue = new MessageQueue('toBackend');
export const fromBackendQueue = new MessageQueue('fromBackend');

// This part is crucial for making the queues available to other modules
// that need them (like WebSocketManager and EventListeners).
// You can pass them as arguments, or make them available globally
// if your architecture relies on that (which the original WebSocketManager does).

// Let's ensure the WebSocketManager has access to the queues it needs
// by setting them up on the WebSocketManager object *after* they are instantiated.
// This is a common pattern for utility objects that need dependencies.

// WebSocketManager connects directly; it doesn't need to be 'new'ed
// No 'wsManager' variable is needed here since WebSocketManager is already the global object.
// We just call its method.

document.addEventListener('DOMContentLoaded', () => {
    console.group('Main App: DOMContentLoaded');
    console.log("Main App: Initializing...");

    // Initialize WebSocketManager with queues
    WebSocketManager.setQueues({
        toFrontendQueue,
        fromFrontendQueue,
        toBackendQueue,
        fromBackendQueue
    });

    // Initialize Event Listeners
    initializeEventListeners();

    // Connect to WebSocket
    WebSocketManager.connect();

    // Start processing backend messages
    processBackendMessages();

    console.log("Main App: Initialization complete.");
    console.groupEnd();
});
