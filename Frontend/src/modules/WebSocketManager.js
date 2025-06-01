// frontend/src/modules/WebSocketManager.js

import {
    updateSystemLog,
    updateStatusLog,
    updateTestLog,
    updateAllQueueDisplays,
    setQueues as setQueueDisplayQueues // Alias to avoid name conflict with WebSocketManager's setQueues
} from './QueueDisplay.js';

import { processBackendMessages } from './EventListeners.js'; // Import the message processor

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.pingInterval = null;
        this.lastPongTime = null;
        this.maxReconnectAttempts = 10;
        this.observer = null;

        // Initialize queue references
        this._frontendDisplayQueue = null;
        this._frontendActionQueue = null;
        this._toBackendQueue = null;
        this._fromBackendQueue = null;

        // Bind methods to maintain 'this' context.
        this.setQueues = this.setQueues.bind(this);
        this.connect = this.connect.bind(this);
        this.sendMessage = this.sendMessage.bind(this);
        this.handleIncomingMessage = this.handleIncomingMessage.bind(this);
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
    setObserver(observer) {
        this.observer = observer;
        return this; // For method chaining
    }

    setQueues({ frontendDisplayQueue, frontendActionQueue, toBackendQueue, fromBackendQueue }) {
        this._frontendDisplayQueue = frontendDisplayQueue;
        this._frontendActionQueue = frontendActionQueue;
        this._toBackendQueue = toBackendQueue;
        this._fromBackendQueue = fromBackendQueue;
        console.log('WebSocketManager: Queues set via setQueues method.');
        updateSystemLog('WebSocketManager: Queues initialized.'); // Log for UI

        // Also pass queues to QueueDisplay module
        setQueueDisplayQueues({ frontendDisplayQueue, frontendActionQueue, toBackendQueue, fromBackendQueue });

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
            this.pingInterval = null;
        }

        console.log(`Attempting to connect to WebSocket at ${url}...`);
        updateSystemLog(`Attempting to connect to WebSocket at ${url}...`);

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
            updateSystemLog('WebSocket connection opened. Sending initial acknowledgment.');

            // Start ping interval (every 25 seconds)
            this.pingInterval = setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.sendMessage({
                        type: 'ping',
                        data: { ping: true }, // More meaningful ping data
                        timestamp: Date.now()
                    });

                    // Check if we got a pong response
                    // Give server some buffer, e.g., ping every 25s, expect pong within 40s
                    if (this.lastPongTime && (Date.now() - this.lastPongTime) > 40000) {
                        console.warn('WebSocketManager: No pong received in 40 seconds, reconnecting...');
                        updateSystemLog('No pong received. Forcing reconnect...');
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
                    status: 'ready',
                    capabilities: ['ping-pong'] // Additional metadata
                },
                timestamp: Date.now(),
                id: `frontend-init-${Date.now()}` // Explicit ID
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

                // Notify observer if available
                if (this.observer) {
                    this.observer.handleMessage(message);
                }

                // Handle pong messages
                if (message.type === 'pong') {
                    this.lastPongTime = Date.now();
                    console.debug('WebSocketManager: Received pong from server');
                    updateStatusLog('Received pong from server.');
                    return; // Don't pass pong to handleIncomingMessage or other queues
                }

                // Pass the ALREADY PARSED object to handleIncomingMessage
                this.handleIncomingMessage(message);

            } catch (e) {
                // This catch block is for parsing errors on the initial raw event.data
                console.error('WebSocketManager: Failed to parse WebSocket message:', e, event.data);
                updateSystemLog(`WebSocket error: Failed to parse message - ${e.message}. Data: ${String(event.data).substring(0, 50)}...`);
                const errorElement = document.getElementById('wsErrors');
                if (errorElement) {
                    errorElement.textContent = `WebSocket error: ${e.message}`;
                }
            }
        };

        this.ws.onclose = (event) => {
            console.warn('WebSocketManager: CLOSE event received:', event);
            const statusElement = document.getElementById('connectionStatus');
            statusElement.textContent = 'Disconnected';
            statusElement.style.color = 'red';
            
            // Show reconnect status
            const reconnectElement = document.getElementById('reconnectStatus');
            if (reconnectElement) {
                reconnectElement.textContent = `Reconnecting in ${Math.round(delay/1000)}s...`;
                reconnectElement.style.display = 'block';
            }
            updateSystemLog(`WebSocket disconnected. Code: ${event.code}, Reason: ${event.reason || 'N/A'}`);

            // Always attempt to reconnect unless it was a normal closure (1000) or going away (1001)
            if (event.code !== 1000 && event.code !== 1001) {
                this.reconnectAttempts++;
                const baseDelay = 1000;
                const maxDelay = 30000;
                // Exponential backoff with jitter (adding random factor)
                const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts) + Math.random() * 500, maxDelay);

                console.log(`WebSocketManager: Attempting to reconnect in ${delay / 1000} seconds... (Attempt ${this.reconnectAttempts})`);
                updateSystemLog(`Attempting reconnect in ${Math.round(delay/1000)}s... (Attempt ${this.reconnectAttempts})`);

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
                updateSystemLog('WebSocket closed normally.');
            }
            console.groupEnd();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocketManager: ERROR event received:', error);
            document.getElementById('connectionStatus').textContent = 'Error';
            document.getElementById('connectionStatus').style.color = 'orange';
            updateSystemLog(`WebSocket connection error: ${error.message || 'Unknown error'}`);

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
     * Enqueues the message to the internal _toBackendQueue for display *before* sending,
     * then sends it over the WebSocket.
     * @param {Object} message - The message object to send.
     */
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocketManager: Sending message:', message);

            // Enqueue to _toBackendQueue immediately for display/tracking that it's being sent
            if (this._toBackendQueue) {
                this._toBackendQueue.enqueue(message);
                updateAllQueueDisplays(); // Update display to show it's queued for sending
            } else {
                console.warn('WebSocketManager: _toBackendQueue is not set. Outgoing message display ignored.');
            }

            // Actual send operation
            this.ws.send(JSON.stringify(message));

            // NOTE: The message is considered "sent" once ws.send() is called.
            // Removal from _toBackendQueue (display) would typically happen on backend ACK
            // or if you want immediate visual feedback, you could dequeue it here
            // (but that implies it's no longer "pending send").
            // For now, it stays in _toBackendQueue until manually cleared or handled by
            // a sophisticated "sent" status in the UI. The backend response will be handled
            // by _fromBackendQueue.
        } else {
            console.warn('WebSocketManager: WebSocket not open. Message not sent:', message);
            updateSystemLog('WebSocket not open. Message not sent.');
        }
    }

    /**
     * Handles incoming messages from the WebSocket.
     * Receives the ALREADY PARSED message object and enqueues it to _fromBackendQueue.
     * @param {Object} message - The parsed message object received from the WebSocket.
     */
    handleIncomingMessage(message) {
        try {
            if (!message.type) {
                throw new Error('Message type is missing');
            }

            // Directly handle certain message types
            switch(message.type) {
                case 'status':
                    this._handleStatusMessage(message);
                    break;
                case 'error':
                    this._handleErrorMessage(message);
                    break;
                case 'data':
                    this._handleDataMessage(message);
                    break;
                default:
                    // Enqueue other messages for processing
                    if (this._fromBackendQueue) {
                        this._fromBackendQueue.enqueue(message);
                        updateAllQueueDisplays();
                    }
            }
            // The MessageProcessor in EventListeners.js will dequeue and process this.
            // It runs in a separate, continuous loop, so no need to call it here.

        } catch (e) {
            // This catch block is for errors within handleIncomingMessage *after* initial parse
            console.error('WebSocketManager: Error processing incoming message:', e, message); // Log the object directly
            updateSystemLog(`Error processing incoming message: ${e.message}. Data: ${JSON.stringify(message || {}).substring(0, 50)}...`);
        }
    }

    _handleStatusMessage(message) {
        const statusElement = document.getElementById('simulationStatus');
        const logElement = document.getElementById('statusLog');
        
        if (statusElement) {
            statusElement.textContent = message.data.status || 'Status updated';
            statusElement.className = `status-${message.data.status?.toLowerCase() || 'info'}`;
        }
        
        if (logElement) {
            const entry = document.createElement('p');
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${message.data.message}`;
            logElement.prepend(entry);
            
            // Limit log size
            if (logElement.children.length > 50) {
                logElement.removeChild(logElement.lastChild);
            }
        }
        
        // Also enqueue for general processing
        if (this._fromBackendQueue) {
            this._fromBackendQueue.enqueue(message);
        }
    }

    _handleDataMessage(message) {
        const resultElement = document.getElementById('translationResult');
        if (resultElement) {
            // Handle different data formats
            if (message.data.text) {
                resultElement.textContent = message.data.text;
            } else if (message.data.result) {
                resultElement.textContent = JSON.stringify(message.data.result, null, 2);
            } else {
                resultElement.textContent = JSON.stringify(message.data, null, 2);
            }
        }
        
        // Also enqueue for general processing/logging
        if (this._fromBackendQueue) {
            this._fromBackendQueue.enqueue(message);
        }
    }

    _handleErrorMessage(message) {
        updateSystemLog(`ERROR: ${message.data.error} - ${message.data.message}`);
        
        const errorElement = document.getElementById('errorDisplay');
        if (errorElement) {
            errorElement.textContent = `${message.data.error}: ${message.data.message}`;
            errorElement.style.display = 'block';
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                errorElement.style.display = 'none';
            }, 5000);
        }
        
        // Also enqueue for general processing
        if (this._fromBackendQueue) {
            this._fromBackendQueue.enqueue(message);
        }
    }

    checkConnection() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.log('WebSocketManager: Connection lost, attempting to reconnect...');
            updateSystemLog('WebSocket connection lost, attempting reconnect...');
            this.connect();
            return false;
        }

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
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }

            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

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
