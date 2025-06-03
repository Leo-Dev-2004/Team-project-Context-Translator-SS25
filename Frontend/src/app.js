// frontend/src/app.js

import { WebSocketManager } from './modules/WebSocketManager.js';
import { MessageQueue } from './modules/MessageQueue.js';
import { setupEventListeners } from './modules/EventListeners.js';
import { updateSystemLog, updateStatusLog, updateQueueDisplay } from './modules/QueueDisplay.js';

// --- Global Queue Instances ---
// These queues manage the flow of messages within the frontend application.
// They are initialized once and then passed to other modules (like WebSocketManager, EventListeners)
// to ensure a single, consistent source of truth for message handling.
const frontendDisplayQueue = new MessageQueue('frontendDisplayQueue'); // For displaying messages in UI
const frontendActionQueue = new MessageQueue('frontendActionQueue');  // For actions triggered by UI
const toBackendQueue = new MessageQueue('toBackendQueue');            // Messages ready to be sent to backend
const fromBackendQueue = new MessageQueue('fromBackendQueue');        // Messages received from backend

// --- WebSocket Manager Instance ---
// The WebSocketManager handles the actual WebSocket connection, sending, and receiving.
// It uses the toBackendQueue and fromBackendQueue to manage its message flow.
const webSocketManager = WebSocketManager; // <<< FIX: Assign the imported singleton directly, without 'new'

// --- Application Initialization Logic ---
// This ensures that the application starts correctly once the DOM is fully loaded.
document.addEventListener('DOMContentLoaded', () => {
    console.log('app.js: DOMContentLoaded (first time)'); // Log for debugging

    // --- Initialize WebSocketManager with Client ID ---
    // A unique client ID is generated or retrieved to identify this frontend instance.
    // This is crucial for the backend to route messages correctly to specific clients.
    const clientId = `client_${Date.now()}${Math.random().toString(36).substring(2, 9)}`;
    webSocketManager.setClientId(clientId);
    updateSystemLog(`Frontend Client ID: ${clientId}`);

    // --- Set up Queues for WebSocketManager ---
    // The WebSocketManager needs references to the queues it will interact with.
    // It will enqueue outgoing messages into toBackendQueue and dequeue incoming messages from fromBackendQueue.
    webSocketManager.setQueues({
 // Map your existing queue instances to the names WebSocketManager expects
        incomingFrontendQueue: toBackendQueue,   // Messages frontend sends TO backend
        outgoingFrontendQueue: fromBackendQueue, // Messages frontend receives FROM backend

        // Keep these if other modules also use them from this setupEventListeners call
        // but WebSocketManager.setQueues itself doesn't use them directly
        // frontendDisplayQueue,
        // frontendActionQueue,
    });
    console.log('app.js: Queues passed to WebSocketManager for internal management.');

    // --- Set up Event Listeners ---
    // Event listeners for UI interactions (buttons, input fields) are set up in a separate module.
    // They receive references to the queues and the WebSocketManager to send messages.
    setupEventListeners({
        webSocketManager,
        frontendActionQueue,
        toBackendQueue,
        fromBackendQueue,
        frontendDisplayQueue // Pass frontendDisplayQueue as well
    });
    console.log('app.js: Queues and WebSocketManager passed to EventListeners for UI interaction.');

// NEW: Event Listener for Send Test Settings Button
    const sendTestSettingsBtn = document.getElementById('sendTestSettingsBtn');
    if (sendTestSettingsBtn) {
        sendTestSettingsBtn.addEventListener('click', () => {
            console.log('app.js: "Send Test Settings" button clicked.');
            updateSystemLog('Attempting to send test settings message...');

            // Create a WebSocketMessage object
            const testSettingsMessage = {
                id: `test-settings-${Date.now()}`, // Unique ID for the message
                type: 'update_settings',           // Custom type for this message
                data: {                            // Payload with test settings
                    theme: 'dark_mode',
                    notifications: true,
                    language: 'en-US',
                    level: Math.floor(Math.random() * 10) + 1 // Random level
                },
                timestamp: Date.now(),
                client_id: webSocketManager.clientId // Crucial: include client_id
            };

            // Enqueue the message to the toBackendQueue
            // The WebSocketManager will pick this up and send it over the WebSocket.
            toBackendQueue.enqueue(testSettingsMessage);
            updateSystemLog('Test settings message enqueued to toBackendQueue.');
        });
    }

    // --- Initialize WebSocket Connection ---
    // The WebSocket connection is initiated. The WebSocketManager handles reconnection logic.
    webSocketManager.connect();
    console.log('app.js: WebSocket connection initiated.');

    // --- Queue Display Updates ---
    // Subscribe to changes in the frontend queues to update their visual representation.
    // This ensures that the UI accurately reflects the state of messages in transit.
    toBackendQueue.subscribe((queueName, size, items) => {
        updateQueueDisplay('toBackendQueueDisplay', size, items);
    });
    fromBackendQueue.subscribe((queueName, size, items) => {
        updateQueueDisplay('fromBackendQueueDisplay', size, items);
    });
    // Add subscriptions for other queues if they are managed by app.js and need visual updates
    // For example, if frontendOutgoingQueue and frontendIncomingQueue are separate visual queues
    // that are managed by EventListeners or other modules, they would subscribe there.

    
    console.log('app.js: Application initialization complete.');
});

// --- Observer for WebSocket Messages (can be moved to a separate module if complex) ---
// This object defines how the application reacts to different types of messages
// received from the WebSocket. It's passed to the WebSocketManager.
const appObserver = {
    handleMessage: (message) => {
        // console.log('App Observer received message:', message); // Log all messages for debugging

        // Update system log for all incoming messages (except pong which is handled internally)
        if (message.type !== 'pong' && message.type !== 'queue_status_update') {
            updateSystemLog(`Received: ${message.type} (ID: ${message.id ? message.id.substring(0,8) : 'N/A'})`);
        }

        // Handle specific message types
        switch (message.type) {
            case 'ack':
                updateStatusLog(`Connection Acknowledged: ${message.data.message}`);
                break;
            case 'backend_ready_confirm':
                updateStatusLog(`Backend Ready: ${message.data.message}`);
                break;
            case 'status':
                // This is a generic status update, handled by _handleStatusMessage in WebSocketManager
                // but can also be processed here if needed.
                break;
            case 'error':
                // Error messages are handled by _handleErrorMessage in WebSocketManager
                break;
            case 'data':
                // Data messages (like translation results) are handled by _handleDataMessage in WebSocketManager
                break;
            case 'pong':
                // Pong messages are handled directly by WebSocketManager for heartbeat.
                break;
            case 'queue_status_update':
                // Queue status updates are handled directly by WebSocketManager and QueueDisplay.
                break;
            case 'settings_updated_ack': // NEW: Acknowledge from backend for settings update
                updateStatusLog(`Backend confirmed settings update: ${JSON.stringify(message.data)}`);
                console.log('Backend confirmed settings update:', message.data);
                break;
        }
    }
};

webSocketManager.setObserver(appObserver);