// Frontend/src/modules/WebSocketManager.js (CORRECTED DOM ACCESS AND QUEUE ASSIGNMENTS)

import { updateSystemLog, updateStatusLog, updateTestLog, updateQueueDisplay } from './QueueDisplay.js';

// Singleton pattern for WebSocketManager
const WebSocketManager = (() => {
    let ws = null;
    let clientId = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 3;
    const RECONNECT_INTERVAL_MS = 3333; // 3.333 seconds

    // Frontend queues that this manager interacts with
    let _wsOutboundQueue = null;   // Messages the frontend sends to the backend
    let _wsInboundQueue = null; // Messages the frontend receives from the backend

    // Reference to the main UI component instance
    // This will be set by app.js after the UI component has connected and rendered.
    let uiComponent = null; // <--- NEW: Reference to the UI component

    // Optional: An observer for application-level message handling
    let appObserver = null; // This was not used in previous implementations, but kept for completeness.

    const connect = () => {
        console.log('WebSocketManager: Attempting to connect to WebSocket...');
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
            console.warn('WebSocketManager: Already connected or connecting. Skipping connection attempt.');
            return;
        }
        if (!clientId) {
            console.error('WebSocketManager: Client ID not set. Cannot connect.');
            return;
        }

        const wsUrl = `ws://localhost:8000/ws/${clientId}`;
        console.log(`WebSocketManager: Attempting to connect to ${wsUrl}`);
        ws = new WebSocket(wsUrl);

        ws.onopen = (event) => {
            console.log('WebSocketManager: Connection established! (onopen event)');
            updateSystemLog('WebSocket OPEN event received.');
            updateStatusLog('Connected to backend WebSocket.');
            reconnectAttempts = 0;

            // --- IMPORTANT: Use uiComponent to query elements after it's been rendered ---
            const reconnectStatusElement = uiComponent?.shadowRoot?.getElementById('reconnectStatus');
            if (reconnectStatusElement) {
                reconnectStatusElement.style.display = 'none';
                console.log('WebSocketManager: reconnectStatus element hidden.');
            } else {
                console.warn('WebSocketManager: reconnectStatus element not found in UI component shadow DOM on open.');
            }
            // --- End IMPORTANT ---

            // Send a ready_ack message immediately after connection is established
            const readyAckMessage = {
                id: crypto.randomUUID(),
                type: 'frontend.ready_ack',
                payload: { message: 'Frontend is ready to receive messages.' },
                timestamp: Date.now() / 1000, // Convert to seconds
                client_id: clientId,
                origin: 'frontend',
                destination: 'backend'
            };
            if (_wsOutboundQueue) {
                _wsOutboundQueue.enqueue(readyAckMessage);
                console.log('WebSocketManager: Enqueued frontend.ready_ack message to _wsOutboundQueue.');
            } else {
                console.error('WebSocketManager: _wsOutboundQueue is not set. Cannot send ready_ack.');
            }
        };

        ws.onmessage = (event) => {
            console.log('WebSocketManager: Raw MESSAGE received:', event.data); // Uncomment for debugging raw data
            try {
                const message = JSON.parse(event.data);
                // console.log('WebSocketManager: Parsed MESSAGE:', message); // Uncomment for debugging parsed object

                // Directly handle system.queue_status_update messages for visualization
                if (message.type === 'system.queue_status_update') {
                    // These keys ('from_frontend_q_size', 'to_frontend_q_size', 'dead_letter_q_size')
                    // must match EXACTLY what the backend sends.
                    updateQueueDisplay('from_frontend_queue', message.payload.from_frontend_q_size, []);
                    updateQueueDisplay('to_frontend_queue', message.payload.to_frontend_q_size, []);
                    updateQueueDisplay('dead_letter_queue', message.payload.dead_letter_q_size, []);
                }

                // Enqueue ALL incoming messages into the frontend's incoming queue
                if (_wsInboundQueue) {
                    _wsInboundQueue.enqueue(message);
                } else {
                    console.error('WebSocketManager: _wsInboundQueue is not set. Cannot enqueue incoming message.');
                }
            } catch (error) {
                console.error('WebSocketManager: Error parsing incoming message or handling:', error, 'Raw data:', event.data);
                updateSystemLog(`WebSocket message parsing error: ${error.message}. Raw: ${event.data.substring(0, 100)}...`);
            }
        };

        ws.onclose = (event) => {
            console.log(`WebSocketManager: CLOSE event received. Code: ${event.code}, Reason: ${event.reason}`);
            updateSystemLog(`WebSocket CLOSE event received. Code: ${event.code}, Reason: ${event.reason}`);
            updateStatusLog('Disconnected from backend WebSocket.');

            // --- IMPORTANT: Use uiComponent to query elements ---
            const reconnectStatusElement = uiComponent?.shadowRoot?.getElementById('reconnectStatus');
            if (reconnectStatusElement) {
                reconnectStatusElement.style.display = 'block'; // Show reconnect status
                reconnectStatusElement.style.background = '#fca503'; // Orange for reconnecting
            } else {
                console.warn('WebSocketManager: reconnectStatus element not found in UI component shadow DOM on close.');
            }
            // --- End IMPORTANT ---

            // Implement reconnection logic
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                updateStatusLog(`Attempting to reconnect... (Attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                if (reconnectStatusElement) reconnectStatusElement.textContent = `Reconnecting... (Attempt ${reconnectAttempts})`;
                setTimeout(connect, RECONNECT_INTERVAL_MS);
            } else {
                updateStatusLog('Max reconnection attempts reached. Please refresh the page.');
                if (reconnectStatusElement) {
                    reconnectStatusElement.textContent = 'Connection Lost: Max Reconnects';
                    reconnectStatusElement.style.background = '#ef4444'; // Red color
                }
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocketManager: ERROR event received:', error);
            updateSystemLog(`WebSocket Error: ${error.message || 'Unknown error'}`);
            updateStatusLog('WebSocket connection error.');
            // Note: onError is often followed by onClose, so reconnection logic is typically in onClose.
        };
    };

    // This loop sends messages from the _wsOutboundQueue over the WebSocket
    const sendQueueMessages = async () => {
        if (sendQueueMessages._running) {
            console.warn('WebSocketManager: sendQueueMessages loop already running.');
            return;
        }
        sendQueueMessages._running = true;
        console.log('WebSocketManager: Starting sendQueueMessages loop.');
        while (sendQueueMessages._running) { // Loop until explicitly stopped
            if (_wsOutboundQueue && ws && ws.readyState === WebSocket.OPEN) {
                const message = await _wsOutboundQueue.dequeue(); // Wait for a message

                // Optional: Simulate sending delay (e.g., 2 seconds) for `toBackendQueue`
                // await new Promise(resolve => setTimeout(resolve, 2000));

                try {
                    ws.send(JSON.stringify(message));
                    console.log('WebSocketManager: Sent message from _wsOutboundQueue:', message.type);
                } catch (error) {
                    console.error('WebSocketManager: Error sending message:', error);
                    updateSystemLog(`Failed to send message: ${error.message}`);
                    // Optionally re-enqueue if send failed due to temporary issue
                    _wsOutboundQueue.enqueue(message); // Re-enqueue for retry
                }
            } else {
                // If not connected or queue not set, wait a bit before retrying
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }
    };

    return {
        // Public method to set the UI component instance
        setUIComponent: (component) => { // <--- NEW PUBLIC METHOD
            uiComponent = component;
            console.log('WebSocketManager: UI component instance set.');
        },

        isConnected: () => ws && ws.readyState === WebSocket.OPEN,

        // Public methods and properties
        connect: connect,
        get clientId() { return clientId; },
        setClientId: (id) => {
            clientId = id;
            updateTestLog(`Set Client ID: ${clientId}`);
        },
        setQueues: (queues) => {
            // Corrected and confirmed assignments:
            _wsOutboundQueue = queues.toBackendQueue;   // Messages FROM frontend TO backend
            _wsInboundQueue = queues.fromBackendQueue; // Messages FROM backend TO frontend
            console.log('WebSocketManager: Frontend queues set.');

            // Subscribe to the queues to trigger updateQueueDisplay
            // These ensure the queue sizes on the UI are updated as messages are enqueued/dequeued
            if (_wsOutboundQueue) {
                _wsOutboundQueue.subscribe((queueName, size, items) => {
                    updateQueueDisplay(queueName, size, items); // queueName will be 'toBackendQueue'
                });
            } else {
                console.error('WebSocketManager: _wsOutboundQueue is null/undefined after assignment in setQueues.');
            }

            if (_wsInboundQueue) {
                _wsInboundQueue.subscribe((queueName, size, items) => {
                    updateQueueDisplay(queueName, size, items); // queueName will be 'fromBackendQueue'
                });
            } else {
                console.error('WebSocketManager: _wsInboundQueue is null/undefined after assignment in setQueues.');
            }

            // Start the loop to send messages from the outgoing queue
            sendQueueMessages();
        },
        setObserver: (observer) => { // This method is still present but appObserver is currently unused.
            appObserver = observer;
            console.log('WebSocketManager: Observer set.');
        },
        // Public method to send a message directly (bypassing the queue, use with caution)
        sendMessage: (message) => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(message));
                console.log('WebSocketManager: Directly sent message:', message.type);
            } else {
                console.warn('WebSocketManager: Cannot send message, WebSocket not open or initialized.');
                updateSystemLog('Cannot send message: WebSocket not open.');
            }
        },
        // Public method to close the WebSocket connection
        close: () => {
            if (ws) {
                ws.close();
                console.log('WebSocketManager: Connection closed via public method.');
            }
        }
    };
})();

export { WebSocketManager };