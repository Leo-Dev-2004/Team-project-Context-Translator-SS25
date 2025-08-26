// Frontend/src/modules/MessagingService.js

import { MessageQueue } from './MessageQueue.js';
import { WebSocketManager } from './WebSocketManager.js';
import { updateSystemLog } from './QueueDisplay.js'; // To log internal service actions

const MessagingService = (() => {
    let _toBackendQueue;
    let _fromBackendQueue;
    let _frontendDisplayQueue;
    let _frontendActionQueue;
    let _clientId;

    const initialize = (clientId) => {
        if (_toBackendQueue) { // Prevent re-initialization
            console.warn('MessagingService already initialized.');
            return;
        }

        _clientId = clientId;

        // 1. Instantiate all queues
        _toBackendQueue = new MessageQueue('toBackendQueue'); // Messages from FE to BE
        _fromBackendQueue = new MessageQueue('fromBackendQueue'); // Messages from BE to FE
        _frontendDisplayQueue = new MessageQueue('frontendDisplayQueue'); // Internal FE queue for UI display
        _frontendActionQueue = new MessageQueue('frontendActionQueue'); // Internal FE queue for UI actions

        // 2. Configure WebSocketManager with the main communication queues
        WebSocketManager.setClientId(_clientId);
        WebSocketManager.setQueues({
            incomingFrontendQueue: _toBackendQueue,  // This is the queue WebSocketManager reads from to send to backend
            outgoingFrontendQueue: _fromBackendQueue, // This is the queue WebSocketManager writes to when receiving from backend
        });

        // 3. Set up WebSocket connection (MessagingService initiates it)
        WebSocketManager.connect();
        updateSystemLog(`WebSocket connection initiated by MessagingService for client ID: ${_clientId}.`);

        // 4. Set up an observer for incoming messages from WebSocketManager
        // This allows MessagingService to route messages from the backend to the appropriate internal frontend queues
        WebSocketManager.setObserver({
            handleMessage: (message) => {
                // Determine where the message should go based on its type or content
                if (message.type === 'system.log' || message.type === 'status_update' || message.type === 'queue_status_update') {
                    // These are generally for direct display or status updates
                    _frontendDisplayQueue.enqueue(message);
                } else if (message.type === 'test_message_response' || message.type === 'transcription_result' || message.type === 'data') {
                    // Specific data/results for UI components to consume
                    _frontendDisplayQueue.enqueue(message);
                }
                // You might have other queues for specific actions, e.g.,
                // if (message.type === 'action.command') {
                //     _frontendActionQueue.enqueue(message);
                // }
            }
        });

        // 5. Optionally, start any continuous processes like pinging from here
        _startPinging();
    };

    const _startPinging = () => {
        let pingInterval;
        if (pingInterval) clearInterval(pingInterval);
        pingInterval = setInterval(() => {
            if (WebSocketManager.isConnected() && _clientId) {
                const pingMessage = {
                    id: crypto.randomUUID(),
                    type: 'ping',
                    client_id: _clientId,
                    timestamp: Date.now() / 1000,
                    payload: { message: 'Ping from frontend MessagingService' }
                };
                _toBackendQueue.enqueue(pingMessage); // Send ping via the main outgoing queue
                // console.log('MessagingService: Sent ping message.'); // Keep this for debugging
            } else {
                // console.warn('MessagingService: WebSocket not connected or client ID missing, cannot send ping.');
            }
        }, 5000); // Ping every 5 seconds
    };


    // Function to send messages from frontend to backend
    const sendToBackend = (messageType, payload, destination = 'backend', optionalFields = {}) => {
        if (!_clientId) {
            console.error('MessagingService: Client ID not set. Cannot send message to backend.');
            updateSystemLog('ERROR: Client ID not set. Cannot send message.');
            return;
        }
        const message = {
            id: crypto.randomUUID(),
            type: messageType,
            client_id: _clientId,
            destination: destination,
            payload: payload,
            timestamp: Date.now() / 1000,
            forwarding_path: [], // Start with empty path
            ...optionalFields // Allow additional fields like 'original_id' for responses
        };
        _toBackendQueue.enqueue(message);
        // console.log('MessagingService: Enqueued message to backend:', message);
        updateSystemLog(`Sent: ${messageType} (ID: ${message.id.substring(0,8)})`);
    };

    // Public API to expose queues and sending function
    return {
        initialize,
        sendToBackend,
        getToBackendQueue: () => _toBackendQueue,
        getFromBackendQueue: () => _fromBackendQueue,
        getFrontendDisplayQueue: () => _frontendDisplayQueue,
        getFrontendActionQueue: () => _frontendActionQueue,
        getClientId: () => _clientId
    };
})();

export { MessagingService };
