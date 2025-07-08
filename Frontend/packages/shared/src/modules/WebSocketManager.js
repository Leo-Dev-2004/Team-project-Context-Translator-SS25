// Frontend/src/modules/WebSocketManager.js (CORRECTED QUEUE ASSIGNMENTS)

import { updateSystemLog, updateStatusLog, updateTestLog, updateQueueDisplay } from './QueueDisplay.js'; // Ensure updateQueueDisplay is imported

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

    // Optional: An observer for application-level message handling
    let appObserver = null;

    const connect = () => {
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
            console.warn('WebSocketManager: Already connected or connecting.');
            return;
        }

        const wsUrl = `ws://localhost:8000/ws/${clientId}`;
        ws = new WebSocket(wsUrl);

        ws.onopen = (event) => {
            updateSystemLog('WebSocket OPEN event received.');
            updateStatusLog('Connected to backend WebSocket.');
            reconnectAttempts = 0;
            document.getElementById('reconnectStatus').style.display = 'none';

            // Send a ready_ack message immediately after connection is established
            // This tells the backend that the frontend is ready to receive messages.
            const readyAckMessage = {
                id: crypto.randomUUID(),
                type: 'frontend.ready_ack',
                payload: { message: 'Frontend is ready to receive messages.' },
                timestamp: Date.now() / 1000, // Convert to seconds
                client_id: clientId,
                origin: 'frontend',
                destination: 'backend'
            };
            // Enqueue to the outbound queue, which this manager will then send.
            if (_wsOutboundQueue) {
                _wsOutboundQueue.enqueue(readyAckMessage);
                console.log('WebSocketManager: Sending message:', readyAckMessage);
            } else {
                console.error('WebSocketManager: _wsOutboundQueue is not set. Cannot send ready_ack.'); // Corrected variable name
            }
        };

       ws.onmessage = (event) => {
            console.log('WebSocketManager: Raw MESSAGE received:', event.data); // Add this for raw data inspection
            const message = JSON.parse(event.data);
            console.log('WebSocketManager: Parsed MESSAGE:', message); // Add this to see the parsed object

            // Directly handle system.queue_status_update messages for visualization
            if (message.type === 'system.queue_status_update') {
                // The backend sends the queue names as 'from_frontend_q_size', 'to_frontend_q_size', 'dead_letter_q_size' in payload
                // Make sure these match EXACTLY with what the backend sends.
                updateQueueDisplay('from_frontend_queue', message.payload.from_frontend_q_size, []);      // Corrected key!
                updateQueueDisplay('to_frontend_queue', message.payload.to_frontend_q_size, []);        // Corrected key!
                updateQueueDisplay('dead_letter_queue', message.payload.dead_letter_q_size, []);      // This one was already correct
                // Note: The `items` array for backend queues will likely be empty or just meta-data
                // unless your backend is explicitly sending a list of messages within the queue_status_update.
                // For now, passing `[]` is fine if the backend just sends size.
            }

            // Enqueue ALL incoming messages into the frontend's incoming queue
            // The MessageProcessor in EventListeners.js will then dequeue and handle them.
            if (_wsInboundQueue) {
                _wsInboundQueue.enqueue(message);
                // The subscription in app.js for 'fromBackendQueue' will now trigger updateQueueDisplay
            } else {
                console.error('WebSocketManager: _wsInboundQueue is not set. Cannot enqueue incoming message.'); // Corrected variable name
            }
        };

        ws.onclose = (event) => {
            updateSystemLog(`WebSocket CLOSE event received. Code: ${event.code}, Reason: ${event.reason}`);
            updateStatusLog('Disconnected from backend WebSocket.');
            // Implement reconnection logic
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                updateStatusLog(`Attempting to reconnect... (Attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                document.getElementById('reconnectStatus').style.display = 'block';
                setTimeout(connect, RECONNECT_INTERVAL_MS);
            } else {
                updateStatusLog('Max reconnection attempts reached. Please refresh the page.');
                document.getElementById('reconnectStatus').textContent = 'Connection Lost: Max Reconnects';
                document.getElementById('reconnectStatus').style.background = '#ef4444'; // Red color
                document.getElementById('reconnectStatus').style.display = 'block';
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket ERROR event received:', error);
            updateSystemLog(`WebSocket Error: ${error.message || 'Unknown error'}`);
            updateStatusLog('WebSocket connection error.');
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
                
            // <--- ADD THE DELAY HERE FOR `toBackendQueue` ---
            await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate sending delay (e.g., 2 seconds)

            try {
                ws.send(JSON.stringify(message));
                // The subscription for 'toBackendQueue' in app.js already handles its display.
                // No need to call updateQueueDisplay here again for this queue.
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
        // In Frontend/src/modules/WebSocketManager.js, within the return object:
        isConnected: () => ws && ws.readyState === WebSocket.OPEN,

        // Public methods and properties
        connect: connect,
        get clientId() { return clientId; },
        setClientId: (id) => {
            clientId = id;
            updateTestLog(`Set Client ID: ${clientId}`);
        },
        setQueues: (queues) => {
            // CORRECTED ASSIGNMENTS HERE:
            _wsOutboundQueue = queues.toBackendQueue; // This is the queue holding messages TO be sent to backend
            _wsInboundQueue = queues.fromBackendQueue; // This is the queue holding messages RECEIVED FROM backend
            console.log('WebSocketManager: Frontend queues set.');

            // *** IMPORTANT: SUBSCRIBE TO THE QUEUES WITH THEIR ACTUAL NAMES ***
            // These subscriptions will trigger updateQueueDisplay correctly.
            // No need for 'incomingQueueDisplay' or 'outgoingQueueDisplay' string literals here.
            if (_wsOutboundQueue) { // Added null check before subscribing
                _wsOutboundQueue.subscribe((queueName, size, items) => {
                    updateQueueDisplay(queueName, size, items); // queueName will be 'toBackendQueue'
                });
            } else {
                console.error('WebSocketManager: _wsOutboundQueue is null/undefined after assignment.');
            }

            if (_wsInboundQueue) { // Added null check before subscribing
                _wsInboundQueue.subscribe((queueName, size, items) => {
                    updateQueueDisplay(queueName, size, items); // queueName will be 'fromBackendQueue'
                });
            } else {
                console.error('WebSocketManager: _wsInboundQueue is null/undefined after assignment.');
            }

            // Start the loop to send messages from the outgoing queue
            sendQueueMessages();
        },
        setObserver: (observer) => {
            appObserver = observer;
        }
    };
})();


export { WebSocketManager };