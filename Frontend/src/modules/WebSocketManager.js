import {
    updateSystemLog,
    updateStatusLog,
    updateQueueDisplay
} from './QueueDisplay.js';

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
     * - `incomingFrontendQueue`: Messages the frontend sends *to* the backend.
     * - `outgoingFrontendQueue`: Messages the frontend receives *from* the backend.
     */
    setQueues({ incomingFrontendQueue, outgoingFrontendQueue }) {
        // Renamed for clarity in the frontend context:
        // `incomingFrontendQueue` is what the frontend *prepares to send* (its outgoing view)
        // `outgoingFrontendQueue` is what the frontend *receives* (its incoming view)
        this._incomingFrontendQueue = incomingFrontendQueue;
        this._outgoingFrontendQueue = outgoingFrontendQueue;

        console.log('WebSocketManager: Frontend queues set.');
        updateSystemLog('WebSocketManager: Frontend queues initialized and linked.');

        // Subscribe to changes on frontend's *outgoing* queue for display purposes (what's sent TO backend)
        // This corresponds to the 'incoming' queue on the backend side.
        if (this._incomingFrontendQueue) {
            this._incomingFrontendQueue.subscribe((queueName, size, items) => {
                updateQueueDisplay('incomingQueueDisplay', size, items); // 'incoming' on backend perspective
            });
        }
        // Subscribe to changes on frontend's *incoming* queue for display purposes (what's received FROM backend)
        // This corresponds to the 'outgoing' or 'websocket_out' queue on the backend side.
        if (this._outgoingFrontendQueue) {
            this._outgoingFrontendQueue.subscribe((queueName, size, items) => {
                updateQueueDisplay('outgoingQueueDisplay', size, items); // 'outgoing' on backend perspective
            });
        }

        return this;
    }


    /**
     * Establishes a WebSocket connection.
     * It now dynamically constructs the URL using the stored clientId.
     * @param {string} [baseUrl='ws://localhost:8000/ws'] - The base WebSocket URL, without the client_id.
     */
    connect(baseUrl = 'ws://localhost:8000/ws') {
        console.group('WebSocketManager: Connect');

        if (!this.clientId) {
            console.error('WebSocketManager: Cannot connect. Client ID is not set.');
            updateSystemLog('ERROR: WebSocket connection failed. Client ID is missing.');
            return;
        }

        const url = `${baseUrl}/${this.clientId}`;

        // Clear any pending reconnection attempt and ping interval to prevent duplicates
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.pingInterval) { // This will now be null as ping logic is commented out
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }

        updateSystemLog(`Attempting to connect to WebSocket at ${url}...`);

        // Close existing connection if it exists and is open/connecting
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            this.ws.onclose = null; // Prevent duplicate close handlers
            this.ws.close();
            console.log('WebSocketManager: Closing existing connection before re-connecting.');
            updateSystemLog('Closing previous WebSocket connection.');
        }

        this.ws = new WebSocket(url);

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

            // Ping interval and pong checks are **intentionally commented out**
            // to align with the current backend WebSocketManager's behavior
            // where ping/pong is handled by the BackendServiceDispatcher
            // as part of the UniversalMessage flow, not by the raw WebSocket layer.
            /*
            this.pingInterval = setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const pingMessage = {
                        id: `ping-${Date.now()}`,
                        type: 'ping',
                        payload: { timestamp: Date.now() },
                        timestamp: Date.now(),
                        client_id: this.clientId,
                        origin: 'frontend',
                        destination: 'backend.dispatcher'
                    };
                    this.sendMessage(pingMessage);

                    if (this.lastPongTime && (Date.now() - this.lastPongTime) > 7500) {
                        console.warn('WebSocketManager: No pong received in 7.5 seconds, connection might be stale. Forcing reconnect.');
                        updateSystemLog('No pong received. Attempting to re-establish connection...');
                        this.connect(baseUrl);
                    }
                }
            }, 2500);
            */

            // Send initial frontend_ready_ack (as a UniversalMessage structure)
            this.sendMessage({
                id: `frontend-init-${Date.now()}`,
                type: 'frontend.ready_ack',
                client_id: this.clientId,
                payload: {
                    message: 'Frontend ready to receive',
                    version: '1.0',
                    status: 'ready',
                    capabilities: ['ping-pong'] // This still indicates capability even if not actively used here
                },
                timestamp: Date.now(),
                origin: 'frontend',
                destination: 'backend.dispatcher'
            });

            document.dispatchEvent(new CustomEvent('websocket-ack'));
            console.groupEnd();
        };

        this.ws.onmessage = (event) => {
            console.log('WebSocket MESSAGE event received:', event.data);
            let message;
            try {
                message = JSON.parse(event.data);
                if (!message || typeof message.type === 'undefined' || typeof message.payload === 'undefined') {
                    throw new Error('Message is null, not an object, or missing "type" or "payload" property.');
                }
            } catch (e) {
                console.error('WebSocketManager: Failed to parse or validate WebSocket message:', e, event.data);
                updateSystemLog(`WebSocket parsing error: ${e.message}. Data: ${String(event.data).substring(0, 100)}...`);
                return;
            }

            if (this.observer) {
                this.observer.handleMessage(message);
            }

            // Backend queue status updates should now use the new queue names
            if (message.type === 'queue_status_update') {
                const { queue_name, size, items } = message.payload;
                let displayId;
                switch (queue_name) {
                    case 'incoming':    displayId = 'incomingQueueDisplay';     break;
                    case 'outgoing':    displayId = 'outgoingQueueDisplay';     break;
                    case 'dead_letter': displayId = 'deadLetterQueueDisplay';   break;
                    default:
                        console.warn(`WebSocketManager: Unknown backend queue name in status update: ${queue_name}`);
                        return;
                }
                updateQueueDisplay(displayId, size, items);
                updateStatusLog(`Backend Queue '${queue_name}' updated: Size ${size}.`);
                return;
            }

            // The 'pong' message from the backend is now a UniversalMessage with type 'pong'.
            // The BackendServiceDispatcher sends this in response to a 'ping' from the frontend.
            if (message.type === 'pong') {
                this.lastPongTime = Date.now(); // Still track for potential future use or debugging
                console.debug('WebSocketManager: Received pong from server via UniversalMessage.');
                updateStatusLog('Received pong from server.');
                return;
            }

            // Handle backend_ready_confirm
            if (message.type === 'backend.ready_confirm') {
                console.log('WebSocketManager: Backend ready confirmation received:', message.payload.message);
                updateStatusLog(`Backend confirmed ready: ${message.payload.message}`);
                return;
            }


            this.handleIncomingMessage(message); // Enqueue all other relevant messages
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

            if (event.code !== 1000 && event.code !== 1001) { // 1000: normal closure, 1001: going away
                this.reconnectAttempts++;
                const baseDelay = 3000;
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
                this.reconnectTimer = setTimeout(() => {
                    console.log('WebSocketManager: Executing reconnect attempt...');
                    this.connect(baseUrl);
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
            .reconnectTimer = null; // Clear timer on error to prevent double calls
            }
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000);
                updateSystemLog(`WebSocket error, attempting reconnect in ${Math.round(delay/1000)}s...`);
                this.reconnectTimer = setTimeout(() => this.connect(baseUrl), delay);
            } else {
                console.error('WebSocketManager: Max reconnect attempts reached after error. Giving up.');
                updateSystemLog('Max reconnect attempts reached after error. Please refresh page.');
            }
            console.groupEnd();
        };
    }

    /**
     * Sends a message to the backend via WebSocket.
     * Enqueues the message to the internal _incomingFrontendQueue for display *before* sending.
     * The message should conform to the new UniversalMessage structure.
     * This is the "outgoing" part from the frontend's perspective.
     * @param {Object} message - The message object to send (UniversalMessage structure).
     */
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            // Ensure essential UniversalMessage fields are present
            if (!message.id) {
                message.id = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
            }
            if (!message.timestamp) {
                message.timestamp = Date.now();
            }
            if (!message.client_id && this.clientId) {
                message.client_id = this.clientId;
            }
            if (!message.origin) {
                message.origin = 'frontend';
            }
            if (!message.destination) {
                message.destination = 'backend.dispatcher'; // Default initial destination
            }
            // Ensure payload is an object, even if empty, for consistency
            if (typeof message.payload === 'undefined' || message.payload === null) {
                message.payload = {};
            }

            console.log('WebSocketManager: Sending message:', message);
            updateSystemLog(`Sending: ${message.type} (ID: ${message.id.substring(0,8)})`);

            // Enqueue the message to the frontend's internal 'incoming' queue for display
            if (this._incomingFrontendQueue) {
                this._incomingFrontendQueue.enqueue(message);
            } else {
                console.warn('WebSocketManager: _incomingFrontendQueue is not set. Outgoing message display ignored.');
            }

            this.ws.send(JSON.stringify(message));

        } else {
            console.warn('WebSocketManager: WebSocket not open. Message not sent:', message);
            updateSystemLog('WebSocket not open. Message not sent. Please connect first.');
        }
    }

    /**
     * Handles incoming messages from the WebSocket.
     * Receives the ALREADY PARSED message object and enqueues it to _outgoingFrontendQueue.
     * This is the "incoming" part from the frontend's perspective.
     * @param {Object} message - The parsed message object received from the WebSocket (UniversalMessage structure).
     */
    handleIncomingMessage(message) {
        try {
            // Enqueue the message to the frontend's internal 'outgoing' queue for consumption by other modules
            if (this._outgoingFrontendQueue) {
                this._outgoingFrontendQueue.enqueue(message);
                updateSystemLog(`Received & enqueued: ${message.type} (ID: ${message.id ? message.id.substring(0,8) : 'N/A'})`);
            } else {
                console.warn('WebSocketManager: _outgoingFrontendQueue is not set. Incoming message ignored:', message);
                updateSystemLog('Frontend inbound queue not set. Message ignored.');
            }
        } catch (e) {
            console.error('WebSocketManager: Error processing incoming message (in handleIncomingMessage):', e, message);
            updateSystemLog(`Error processing incoming message: ${e.message}. Data: ${JSON.stringify(message || {}).substring(0, 100)}...`);
        }
    }

    // --- Private Handlers for Specific Message Types ---
    // These are simplified as main logic moves to app.js or a dedicated UI controller
    _handleStatusMessage(message) {
        const simulationStatusElement = document.getElementById('simulationStatus');
        if (simulationStatusElement) {
            simulationStatusElement.textContent = message.payload.status || 'Status updated';
            simulationStatusElement.className = `status-${(message.payload.status || 'info').toLowerCase()}`;
        }
        updateStatusLog(`Status: ${message.payload.message || message.payload.status}`);
    }

    _handleErrorMessage(message) {
        updateSystemLog(`ERROR from Backend: ${message.payload.error_type || 'Unknown Error'} - ${message.payload.message || 'No message provided'}`);
        const errorDisplayElement = document.getElementById('errorDisplay');
        if (errorDisplayElement) {
            errorDisplayElement.textContent = `Backend Error: ${message.payload.message || 'An error occurred'}`;
            errorDisplayElement.style.display = 'block';
            setTimeout(() => errorDisplayElement.style.display = 'none', 5000);
        }
    }

    /**
     * Checks the WebSocket connection status and attempts to reconnect if necessary.
     * This can be called periodically (e.g., from a health check loop).
     */
    checkConnection(baseUrl = 'ws://localhost:8000/ws') {
        if (!this.clientId) {
            console.warn('WebSocketManager: Cannot check connection. Client ID is not set.');
            return false;
        }
        if (!this.ws || this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CONNECTING) {
            console.log('WebSocketManager: Connection is closed or closing, attempting to connect...');
            updateSystemLog('WebSocket connection state is closed/closing. Attempting reconnect...');
            this.connect(baseUrl);
            return false;
        }

        // Ping check here is **intentionally commented out** for consistency with backend
        /*
        if (this.ws.readyState === WebSocket.OPEN && this.lastPongTime && (Date.now() - this.lastPongTime) > 7500) {
            console.warn('WebSocketManager: No recent pong response in checkConnection, forcing reconnect...');
            updateSystemLog('No recent pong, forcing reconnect.');
            this.connect(baseUrl);
            return false;
        }
        */

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

        // Queue references for the frontend's internal queues
        this._incomingFrontendQueue = null; // Messages frontend wants to send to backend
        this._outgoingFrontendQueue = null; // Messages frontend has received from backend

        // Bind all methods AFTER they have been defined
        this.setClientId = this.setClientId.bind(this);
        this.setObserver = this.setObserver.bind(this);
        this.setQueues = this.setQueues.bind(this);
        this.connect = this.connect.bind(this);
        this.sendMessage = this.sendMessage.bind(this);
        this.handleIncomingMessage = this.handleIncomingMessage.bind(this);
        this._handleStatusMessage = this._handleStatusMessage.bind(this);
        this._handleErrorMessage = this._handleErrorMessage.bind(this);
        this.checkConnection = this.checkConnection.bind(this);
        this.disconnect = this.disconnect.bind(this);
    }
}

// Create and export a single instance (singleton pattern)
const webSocketManager = new WebSocketManager();
export { webSocketManager as WebSocketManager };