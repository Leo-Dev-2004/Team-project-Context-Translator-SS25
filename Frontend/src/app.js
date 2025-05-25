// Haupt-Einstiegspunkt der Anwendung
import { WebSocketManager } from './modules/WebSocketManager.js'; // This is the exported object
import { MessageQueue } from './modules/MessageQueue.js'; // This is the class
import { initializeEventListeners } from './modules/EventListeners.js'; // This is the function
// We don't need to import SimulationManager or QueueDisplay here,
// as their functions are used/imported by EventListeners.js directly.

// Globale Variablen für die Queues (these are correctly instantiated here)
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

    // Set queues on the WebSocketManager object.
    // Assuming WebSocketManager.js has methods to set these:
    // (You might need to add these setter methods to WebSocketManager.js if they don't exist)
    WebSocketManager.setQueues({
        toFrontendQueue,
        fromFrontendQueue,
        toBackendQueue,
        fromBackendQueue
    });

    // Initialize Event Listeners. This function will import
    // startSimulation, stopSimulation, sendTestMessage directly from their modules.
    initializeEventListeners();

    // Connect to WebSocket. WebSocketManager is the object, so call its method directly.
    WebSocketManager.connect(); // No 'new' keyword

    console.log("Main App: Initialization complete.");
    console.groupEnd();
});