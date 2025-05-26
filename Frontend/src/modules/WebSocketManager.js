// frontend/src/modules/WebSocketManager.js

// Remove queue imports since they'll be provided via setQueues
// Removed: import { updateSystemLog, updateStatusLog, updateTestLog, updateAllQueueDisplays } from './QueueDisplay.js';
// We will assume these are passed or accessible differently if needed, or re-add if required by other parts.
// For now, let's just make sure the core queue logic works.

// We need updateAllQueueDisplays and updateSystemLog, etc., for robust logging and UI updates.
// Let's re-add the necessary imports, as they are used within WebSocketManager.
import {
    updateSystemLog,
    updateStatusLog,
    updateTestLog, // Assuming this exists or can be removed if not used by WSManager
    updateAllQueueDisplays
} from './QueueDisplay.js';

import { processBackendMessages } from './EventListeners.js'; // Import the message processor

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.pingInterval = null;
        this.lastPongTime = null;

        // Initialize queue references with null. They will be set externally.
        // Using `_` prefix for internal class properties is good practice.
        this._frontendDisplayQueue = null;   // Corresponds to old `toFrontendQueue` (JS var)
        this._frontendActionQueue = null;    // Corresponds to old `fromFrontendQueue` (JS var)
        this._toBackendQueue = null;         // Corresponds to `toBackendQueue` (JS var)
        this._fromBackendQueue = null;       // Corresponds to `fromBackendQueue` (JS var)

        // Bind methods to maintain 'this' context.
        // This is good practice when passing these methods as callbacks.
        this.setQueues = this.setQueues.bind(this);
        this.connect = this.connect.bind(this);
        this.sendMessage = this.sendMessage.bind(this);
        this.handleIncomingMessage = this.handleIncomingMessage.bind(this); // Ensure this is also bound
    }

    /**
     * Method to set the queue instances from app.js.
     * Expects an object with the queue names as keys.
     * @param {Object} queues - Object containing references to the MessageQueue instances.
     * @param {MessageQueue} queues.frontendDisplayQueue - The queue for messages processed for frontend display.
     * @param {MessageQueue} queues.frontendActionQueue - The queue for messages representing frontend actions.
     * @param {MessageQueue} queues.toBackendQueue - The queue for messages to be sent to the backend.
     * @param {MessageQueue} queues.fromBackendQueue - The queue for messages received from the backend.
     */
    setQueues({ frontendDisplayQueue, frontendActionQueue, toBackendQueue, fromBackendQueue }) {
        this._frontendDisplayQueue = frontendDisplayQueue;
        this._frontendActionQueue = frontendActionQueue;
        this._toBackendQueue = toBackendQueue;
        this._fromBackendQueue = fromBackendQueue;
        console.log('WebSocketManager: Queues set via setQueues method.');
        updateSystemLog('WebSocketManager: Queues initialized.'); // Log for UI
        return this; // Allow method chaining
    }

    connect(url = 'ws://localhost:8000/ws') {
        console.group('WebSocketManager: Connect');

        // Clear any pending reconnection attempt
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // Clear any existing ping interval
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null; // Clear the interval ID
        }

        console.log(`Attempting to connect to WebSocket at ${url}...`);
        updateSystemLog(`Attempting to connect to WebSocket at ${url}...`); // Update UI log

        // Close existing connection if it exists and is open/connecting
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            this.ws.onclose = null; // Remove previous handler to prevent recursive reconnects
            this.ws.close();
            console.log('WebSocketManager: Closing existing connection before re-connecting.');
        }

        this.ws = new WebSocket(url);

        this.ws.onopen = (event) => {
            console.log('WebSocket OPEN event received:', event);
            this.reconnectAttempts = 0;
            this.lastPongTime = Date.now();
            document.getElementById('connectionStatus').textContent = 'Connected';
            document.getElementById('connectionStatus').style.color = 'green';
            updateSystemLog('WebSocket connection opened. Sending initial acknowledgment.'); // Update UI log

            // Start ping interval (every 25 seconds)
            this.pingInterval = setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.sendMessage({
                        type: 'ping',
                        data: {}, // Ensure data field exists
                        timestamp: Date.now()
                    });

                    // Check if we got a pong response
                    // Give server some buffer, e.g., ping every 25s, expect pong within 40s
                    if (this.lastPongTime && (Date.now() - this.lastPongTime) > 40000) {
                        console.warn('WebSocketManager: No pong received in 40 seconds, reconnecting...');
                        updateSystemLog('No pong received. Forcing reconnect...'); // Update UI log
                        this.connect(url);
                    }
                }
            }, 25000);

            // Send initial ack
            this.sendMessage({
                type: 'frontend_ready_ack',
                data: {
                    message: 'Frontend ready to receive',
                    version: '1.0',
                    status: 'ready'
                },
                timestamp: Date.now()
            });

            document.dispatchEvent(new CustomEvent('websocket-ack'));
            console.groupEnd();
        };

        this.ws.onmessage = (event) => {
            console.log('WebSocket MESSAGE event received:', event.data);
            try {
                const message = JSON.parse(event.data);
                if (!message.type) {
                    throw new Error('Message type is missing');
                }

                // Handle pong messages
                if (message.type === 'pong') {
                    this.lastPongTime = Date.now();
                    console.debug('WebSocketManager: Received pong from server');
                    updateStatusLog('Received pong from server.'); // Update UI log
                    return;
                }

                this.handleIncomingMessage(message);
                // Trigger message processing after enqueuing into _fromBackendQueue
                // It's good practice to call processBackendMessages from the main app or EventListeners
                // after the message is enqueued, to ensure it's a continuous loop there.
                // If processBackendMessages is designed to run indefinitely in a loop,
                // it doesn't need to be called on every message.
                // Assuming processBackendMessages is a continuously running loop in EventListeners.js
                // updateAllQueueDisplays(); // This is often called after message processing is done.
            } catch (e) {
                console.error('WebSocketManager: Failed to parse WebSocket message:', e, event.data);
                updateSystemLog(`WebSocket error: Failed to parse message - ${e.message}.`); // Update UI log
                const errorElement = document.getElementById('wsErrors');
                if (errorElement) {
                    errorElement.textContent = `WebSocket error: ${e.message}`;
                }
            }
        };

        this.ws.onclose = (event) => {
            console.warn('WebSocketManager: CLOSE event received:', event);
            document.getElementById('connectionStatus').textContent = 'Disconnected';
            document.getElementById('connectionStatus').style.color = 'red';
            updateSystemLog(`WebSocket disconnected. Code: ${event.code}, Reason: ${event.reason || 'N/A'}`); // Update UI log

            // Always attempt to reconnect unless it was a normal closure (1000) or going away (1001)
            if (event.code !== 1000 && event.code !== 1001) {
                this.reconnectAttempts++;
                const baseDelay = 1000;
                const maxDelay = 30000;
                // Exponential backoff with jitter (adding random factor)
                const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts) + Math.random() * 500, maxDelay);

                console.log(`WebSocketManager: Attempting to reconnect in ${delay / 1000} seconds... (Attempt ${this.reconnectAttempts})`);
                updateSystemLog(`Attempting reconnect in ${Math.round(delay/1000)}s... (Attempt ${this.reconnectAttempts})`); // Update UI log

                // Clear any existing reconnect timer to avoid multiple timers
                if (this.reconnectTimer) {
                    clearTimeout(this.reconnectTimer);
                }

                this.reconnectTimer = setTimeout(() => {
                    console.log('WebSocketManager: Executing reconnect attempt...');
                    this.connect(url);
                }, delay);
            } else {
                console.log('WebSocketManager: Closed normally, not reconnecting.');
                updateSystemLog('WebSocket closed normally.'); // Update UI log
            }
            console.groupEnd();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocketManager: ERROR event received:', error);
            document.getElementById('connectionStatus').textContent = 'Error';
            document.getElementById('connectionStatus').style.color = 'orange';
            updateSystemLog(`WebSocket connection error: ${error.message || 'Unknown error'}`); // Update UI log

            // Clear any existing reconnect timer to avoid multiple timers
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
            }
            // Trigger immediate reconnect attempt on error if not max attempts reached
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
                this.reconnectTimer = setTimeout(() => this.connect(url), delay);
            } else {
                 console.error('WebSocketManager: Max reconnect attempts reached after error. Giving up.');
                 updateSystemLog('Max reconnect attempts reached after error. Please refresh page.');
            }

            console.groupEnd();
        };
    }

    /**
     * Sends a message to the backend via WebSocket.
     * Enqueues the message to the internal _toBackendQueue before sending.
     * @param {Object} message - The message object to send.
     */
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocketManager: Sending message:', message);
            if (this._toBackendQueue) { // Use the internal _toBackendQueue
                this._toBackendQueue.enqueue(message); // Enqueue for display/tracking
                updateAllQueueDisplays(); // Update display after enqueuing
            } else {
                console.warn('WebSocketManager: _toBackendQueue is not set. Message not enqueued, but still sent.');
                updateSystemLog('Warning: _toBackendQueue not set. Msg not enqueued.');
            }
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocketManager: WebSocket not open. Message not sent:', message);
            updateSystemLog('WebSocket not open. Message not sent.');
            // Optionally enqueue to frontendActionQueue if you want to retry sending later
            // if (this._frontendActionQueue) {
            //     this._frontendActionQueue.enqueue(message);
            // }
        }
    }

    /**
     * Handles incoming messages from the WebSocket.
     * Parses the message and enqueues it to the internal _fromBackendQueue.
     * @param {string} messageData - The raw message data received from the WebSocket.
     */
    handleIncomingMessage(messageData) {
        // console.log('WebSocketManager: Handling incoming message:', messageData); // Too verbose
        try {
            const message = JSON.parse(messageData);
            if (!message.type) {
                throw new Error('Message type is missing');
            }

            if (this._fromBackendQueue) { // Use the internal _fromBackendQueue
                this._fromBackendQueue.enqueue(message);
                updateAllQueueDisplays(); // Trigger display update immediately after enqueuing
            } else {
                console.error('WebSocketManager: _fromBackendQueue is not set. Cannot enqueue incoming message.');
                updateSystemLog('Error: _fromBackendQueue not ready. Incoming message dropped.');
            }
            // The MessageProcessor in EventListeners.js will dequeue and process this.
            // It runs in a separate, continuous loop, so no need to call it here.

        } catch (e) {
            console.error('WebSocketManager: Failed to parse WebSocket message:', e, messageData);
            updateSystemLog(`Error parsing incoming message: ${e.message}. Data: ${messageData.substring(0, 50)}...`);
        }
    }

    // You can keep or remove checkConnection/disconnect based on if you use them externally.
    // For now, let's keep them as they provide useful functionality.
    checkConnection() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.log('WebSocketManager: Connection lost, attempting to reconnect...');
            updateSystemLog('WebSocket connection lost, attempting reconnect...');
            this.connect();
            return false;
        }

        // Verify we're getting pong responses (this is already handled by setInterval)
        if (this.lastPongTime && (Date.now() - this.lastPongTime) > 60000) {
            console.warn('WebSocketManager: No recent pong response in checkConnection, forcing reconnect...');
            updateSystemLog('No recent pong, forcing reconnect.');
            this.connect();
            return false;
        }

        return true;
    }

    disconnect() {
        if (this.ws) {
            // Clear any pending reconnect attempts
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }

            // Clear ping interval
            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

            // Close connection with normal closure code (1000)
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.close(1000, 'Client initiated disconnect');
                updateSystemLog('WebSocket disconnected by client.');
            }
        }
    }
}

// Create and export a single instance (singleton pattern)
const webSocketManager = new WebSocketManager();
export { webSocketManager as WebSocketManager };