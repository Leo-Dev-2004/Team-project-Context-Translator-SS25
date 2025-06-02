// frontend/src/modules/WebSocketManager.js

import {
    updateSystemLog,
    updateStatusLog,
    updateTestLog, // Assuming this is for generic test logs
    updateQueueDisplay // This is the crucial function we'll use for all queue updates
} from './QueueDisplay.js'; // Assuming QueueDisplay handles rendering specific queue HTML elements

class WebSocketManager {
    // --- ALL METHODS ARE DEFINED HERE, BEFORE THE CONSTRUCTOR ---

    setClientId(id) {
        if (typeof id === 'string' && id.trim() !== '') {
            this.clientId = id;
            console.log(`WebSocketManager: Client ID set to '${this.clientId}'.`);
        } else {
            console.error('WebSocketManager: Invalid client ID provided.');
            updateSystemLog('ERROR: Invalid client ID for WebSocket.');
        }
        return this;
    }

    /**
     * Sets a general observer for WebSocket messages.
     * @param {Object} observer - An object with a `handleMessage` method.
     * @returns {WebSocketManager} For method chaining.
     */
    setObserver(observer) {
        this.observer = observer;
        return this;
    }

    /**
     * Method to set the queue instances from app.js.
     * These are the *frontend's* queues.
     * Also subscribes to changes on these queues to update their display.
     * @param {Object} queues - Object containing references to the MessageQueue instances.
     */
    setQueues({ frontendDisplayQueue, frontendActionQueue, toBackendQueue, fromBackendQueue }) {
        this._frontendDisplayQueue = frontendDisplayQueue;
        this._frontendActionQueue = frontendActionQueue;
        this._toBackendQueue = toBackendQueue;
        this._fromBackendQueue = fromBackendQueue;

        console.log('WebSocketManager: Frontend queues set.');
        updateSystemLog('WebSocketManager: Frontend queues initialized and linked.');

        // Subscribe to changes on frontend's *outgoing* queue for display purposes
        if (this._toBackendQueue) {
            this._toBackendQueue.subscribe((queueName, size, items) => {
                // Map the frontend's 'toBackendQueue' to the backend's 'from_frontend' visual display
                // as that's where it conceptually goes first.
                updateQueueDisplay(queueName, size, items); // This should be for what's about to be sent
            });
        }
        // Subscribe to changes on frontend's *incoming* queue for display purposes
        if (this._fromBackendQueue) {
            this._fromBackendQueue.subscribe((queueName, size, items) => {
                updateQueueDisplay(queueName, size, items); // This is for what's received from backend
            });
        }

        return this;
    }


    /**
     * Establishes a WebSocket connection.
     * It now dynamically constructs the URL using the stored clientId.
     * @param {string} [baseUrl='ws://localhost:8000/ws'] - The base WebSocket URL, without the client_id.
     */
    connect(baseUrl = 'ws://localhost:8000/ws') { // baseUrl is now just the static part
        console.group('WebSocketManager: Connect');

        if (!this.clientId) { // Ensure client ID is set before connecting
            console.error('WebSocketManager: Cannot connect. Client ID is not set.');
            updateSystemLog('ERROR: WebSocket connection failed. Client ID is missing.');
            return;
        }

        // --- Dynamically construct the full URL ---
        const url = `${baseUrl}/${this.clientId}`;
        // ------------------------------------------

        // Clear any pending reconnection attempt and ping interval to prevent duplicates
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }

        updateSystemLog(`Attempting to connect to WebSocket at ${url}...`);

        // Close existing connection if it exists and is open/connecting
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            this.ws.onclose = null;
            this.ws.close();
            console.log('WebSocketManager: Closing existing connection before re-connecting.');
            updateSystemLog('Closing previous WebSocket connection.');
        }

        this.ws = new WebSocket(url); // Connect using the new URL with client_id

        this.ws.onopen = (event) => {
            console.log('WebSocket OPEN event received:', event);
            this.reconnectAttempts = 0;
            this.lastPongTime = Date.now();
            document.getElementById('connectionStatus').textContent = 'Connected';
            document.getElementById('connectionStatus').style.color = 'green';
            updateSystemLog('WebSocket connection opened. Sending initial acknowledgment.');

            const reconnectElement = document.getElementById('reconnectStatus');
            if (reconnectElement) {
                reconnectElement.textContent = '';
                reconnectElement.style.display = 'none';
            }

            // Start ping interval
            this.pingInterval = setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const pingMessage = {
                        id: `ping-${Date.now()}`,
                        type: 'ping',
                        data: { timestamp: Date.now() },
                        timestamp: Date.now()
                    };
                    this.sendMessage(pingMessage);

                    if (this.lastPongTime && (Date.now() - this.lastPongTime) > 7500) {
                        console.warn('WebSocketManager: No pong received in 7.5 seconds, connection might be stale. Forcing reconnect.');
                        updateSystemLog('No pong received. Attempting to re-establish connection...');
                        this.connect(baseUrl); // Pass baseUrl to reconnect, it will use stored clientId
                    }
                }
            }, 2500);

            // Send initial frontend_ready_ack (you might want to include client_id here too)
            this.sendMessage({
                type: 'frontend_ready_ack',
                id: `frontend-init-${Date.now()}`, // Use clientId as the message ID
                client_id: this.clientId,
                data: {
                    message: 'Frontend ready to receive',
                    version: '1.0',
                    status: 'ready',
                    capabilities: ['ping-pong']                },
                timestamp: Date.now(),
            });

            document.dispatchEvent(new CustomEvent('websocket-ack'));
            console.groupEnd();
        };

        this.ws.onmessage = (event) => {
            console.log('WebSocket MESSAGE event received:', event.data);
            let message;
            try {
                message = JSON.parse(event.data);
                if (!message || typeof message.type === 'undefined') {
                    throw new Error('Message is null, not an object, or missing type property.');
                }
            } catch (e) {
                console.error('WebSocketManager: Failed to parse or validate WebSocket message:', e, event.data);
                updateSystemLog(`WebSocket parsing error: ${e.message}. Data: ${String(event.data).substring(0, 100)}...`);
                return;
            }

            if (this.observer) {
                this.observer.handleMessage(message);
            }

            if (message.type === 'queue_status_update') {
                const { queue_name, size, items } = message.data;
                let displayId;
                switch (queue_name) {
                    case 'from_frontend': displayId = 'fromFrontendQueueDisplay'; break;
                    case 'to_backend':    displayId = 'toBackendQueueDisplay';    break;
                    case 'from_backend':  displayId = 'fromBackendQueueDisplay';  break;
                    case 'to_frontend':   displayId = 'toFrontendQueueDisplay';   break;
                    case 'dead_letter':   displayId = 'deadLetterQueueDisplay';   break;
                    default:
                        console.warn(`WebSocketManager: Unknown backend queue name in status update: ${queue_name}`);
                        return;
                }
                updateQueueDisplay(displayId, size, items);
                updateStatusLog(`Backend Queue '${queue_name}' updated: Size ${size}.`);
                return;
            }

            if (message.type === 'pong') {
                this.lastPongTime = Date.now();
                console.debug('WebSocketManager: Received pong from server');
                updateStatusLog('Received pong from server.');
                return;
            }

            this.handleIncomingMessage(message);
        };

        this.ws.onclose = (event) => {
            console.warn('WebSocketManager: CLOSE event received:', event);
            const statusElement = document.getElementById('connectionStatus');
            statusElement.textContent = 'Disconnected';
            statusElement.style.color = 'red';

            const reconnectElement = document.getElementById('reconnectStatus');
            if (reconnectElement) {
                reconnectElement.style.display = 'block';
            }
            updateSystemLog(`WebSocket disconnected. Code: ${event.code}, Reason: ${event.reason || 'N/A'}`);

            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

            if (event.code !== 1000 && event.code !== 1001) {
                this.reconnectAttempts++;
                const baseDelay = 1000;
                const maxDelay = 30000;
                const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts - 1) + Math.random() * 500, maxDelay);

                if (reconnectElement) {
                    reconnectElement.textContent = `Reconnecting in ${Math.round(delay / 1000)}s... (Attempt ${this.reconnectAttempts})`;
                }

                console.log(`WebSocketManager: Attempting to reconnect in ${delay / 1000} seconds... (Attempt ${this.reconnectAttempts})`);
                updateSystemLog(`Attempting reconnect in ${Math.round(delay / 1000)}s... (Attempt ${this.reconnectAttempts})`);

                if (this.reconnectTimer) {
                    clearTimeout(this.reconnectTimer);
                }
                // FIXED LINE BELOW: Removed the stray dot
                this.reconnectTimer = setTimeout(() => {
                    console.log('WebSocketManager: Executing reconnect attempt...');
                    this.connect(baseUrl); // Pass baseUrl for reconnect
                }, delay);
            } else {
                console.log('WebSocketManager: Closed normally, not reconnecting.');
                updateSystemLog('WebSocket closed normally. No reconnection needed.');
                if (reconnectElement) {
                    reconnectElement.textContent = 'Disconnected.';
                    reconnectElement.style.display = 'block';
                }
            }
            console.groupEnd();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocketManager: ERROR event received:', error);
            document.getElementById('connectionStatus').textContent = 'Error';
            document.getElementById('connectionStatus').style.color = 'orange';
            updateSystemLog(`WebSocket connection error: ${error.message || 'Unknown error'}`);

            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
            }
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000);
                updateSystemLog(`WebSocket error, attempting reconnect in ${Math.round(delay/1000)}s...`);
                this.reconnectTimer = setTimeout(() => this.connect(baseUrl), delay); // Pass baseUrl for reconnect
            } else {
                console.error('WebSocketManager: Max reconnect attempts reached after error. Giving up.');
                updateSystemLog('Max reconnect attempts reached after error. Please refresh page.');
            }
            console.groupEnd();
        };
    }

    /**
     * Sends a message to the backend via WebSocket.
     * Enqueues the message to the internal _toBackendQueue for display *before* sending.
     * @param {Object} message - The message object to send.
     */
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            if (!message.id) {
                message.id = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
            }
            if (!message.timestamp) {
                message.timestamp = Date.now();
            }

            console.log('WebSocketManager: Sending message:', message);
            updateSystemLog(`Sending: ${message.type} (ID: ${message.id.substring(0,8)})`);

            if (this._toBackendQueue) {
                this._toBackendQueue.enqueue(message);
            } else {
                console.warn('WebSocketManager: _toBackendQueue is not set. Outgoing message display ignored.');
            }

            this.ws.send(JSON.stringify(message));

        } else {
            console.warn('WebSocketManager: WebSocket not open. Message not sent:', message);
            updateSystemLog('WebSocket not open. Message not sent. Please connect first.');
        }
    }

    /**
     * Handles incoming messages from the WebSocket.
     * Receives the ALREADY PARSED message object and enqueues it to _fromBackendQueue.
     * @param {Object} message - The parsed message object received from the WebSocket.
     */
    handleIncomingMessage(message) {
        try {
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
                    if (this._fromBackendQueue) {
                        this._fromBackendQueue.enqueue(message);
                        updateSystemLog(`Received & enqueued: ${message.type} (ID: ${message.id ? message.id.substring(0,8) : 'N/A'})`);
                    } else {
                        console.warn('WebSocketManager: _fromBackendQueue is not set. Incoming message ignored:', message);
                        updateSystemLog('Frontend inbound queue not set. Message ignored.');
                    }
            }
        } catch (e) {
            console.error('WebSocketManager: Error processing incoming message (in handleIncomingMessage):', e, message);
            updateSystemLog(`Error processing incoming message: ${e.message}. Data: ${JSON.stringify(message || {}).substring(0, 100)}...`);
        }
    }

    // --- Private Handlers for Specific Message Types ---
    _handleStatusMessage(message) {
        const simulationStatusElement = document.getElementById('simulationStatus');
        if (simulationStatusElement) {
            simulationStatusElement.textContent = message.data.status || 'Status updated';
            simulationStatusElement.className = `status-${(message.data.status || 'info').toLowerCase()}`;
        }
        updateStatusLog(`Status: ${message.data.message || message.data.status}`);
    }

    _handleDataMessage(message) {
        const translationOutput = document.getElementById('translationOutput');
        if (translationOutput) {
            translationOutput.textContent = message.data.translated_text || JSON.stringify(message.data, null, 2);
            const translationLoading = document.getElementById('translationLoading');
            if (translationLoading) {
                translationLoading.classList.add('hidden');
            }
        }
        updateSystemLog(`Data Received: ${message.type} (ID: ${message.id ? message.id.substring(0,8) : 'N/A'})`);
    }

    _handleErrorMessage(message) {
        updateSystemLog(`ERROR from Backend: ${message.data.error_type || 'Unknown Error'} - ${message.data.message || 'No message provided'}`);
        const errorDisplayElement = document.getElementById('errorDisplay');
        if (errorDisplayElement) {
            errorDisplayElement.textContent = `Backend Error: ${message.data.message || 'An error occurred'}`;
            errorDisplayElement.style.display = 'block';
            setTimeout(() => errorDisplayElement.style.display = 'none', 5000);
        }
    }

    /**
     * Checks the WebSocket connection status and attempts to reconnect if necessary.
     * This can be called periodically (e.g., from a health check loop).
     */
    checkConnection(baseUrl = 'ws://localhost:8000/ws') { // Pass baseUrl here too
        if (!this.clientId) {
            console.warn('WebSocketManager: Cannot check connection. Client ID is not set.');
            return false;
        }
        if (!this.ws || this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CONNECTING) {
            console.log('WebSocketManager: Connection is closed or closing, attempting to connect...');
            updateSystemLog('WebSocket connection state is closed/closing. Attempting reconnect...');
            this.connect(baseUrl); // Pass baseUrl
            return false;
        }

        if (this.ws.readyState === WebSocket.OPEN && this.lastPongTime && (Date.now() - this.lastPongTime) > 7500) {
            console.warn('WebSocketManager: No recent pong response in checkConnection, forcing reconnect...');
            updateSystemLog('No recent pong, forcing reconnect.');
            this.connect(baseUrl); // Pass baseUrl
            return false;
        }

        return true;
    }

    /**
     * Disconnects the WebSocket connection gracefully.
     */
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
                this.ws.close(1000, 'Client initiated disconnect'); // 1000 is normal closure
                updateSystemLog('WebSocket disconnected by client.');
            }
        }
        document.getElementById('connectionStatus').textContent = 'Disconnected';
        document.getElementById('connectionStatus').style.color = 'red';
        const reconnectElement = document.getElementById('reconnectStatus');
        if (reconnectElement) {
            reconnectElement.textContent = 'Disconnected.';
            reconnectElement.style.display = 'block';
        }
    }

    // --- END OF ALL METHODS DEFINED BEFORE THE CONSTRUCTOR ---


    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.pingInterval = null;
        this.lastPongTime = null;
        this.maxReconnectAttempts = 10;
        this.observer = null;

        this.clientId = null;

        this._frontendDisplayQueue = null;
        this._frontendActionQueue = null;
        this._toBackendQueue = null;
        this._fromBackendQueue = null;

        // Bind all methods AFTER they have been defined
        this.setClientId = this.setClientId.bind(this);
        this.setObserver = this.setObserver.bind(this);
        this.setQueues = this.setQueues.bind(this);
        this.connect = this.connect.bind(this);
        this.sendMessage = this.sendMessage.bind(this);
        this.handleIncomingMessage = this.handleIncomingMessage.bind(this);
        this._handleStatusMessage = this._handleStatusMessage.bind(this);
        this._handleDataMessage = this._handleDataMessage.bind(this);
        this._handleErrorMessage = this._handleErrorMessage.bind(this);
        this.checkConnection = this.checkConnection.bind(this);
        this.disconnect = this.disconnect.bind(this);
    }
}

// Create and export a single instance (singleton pattern)
const webSocketManager = new WebSocketManager();
export { webSocketManager as WebSocketManager };