// frontend/src/modules/WebSocketManager.js

// Remove queue imports since they'll be provided via setQueues
import { processBackendMessages } from './EventListeners.js'; // Import the message processor

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        // Initialize queue references with null checks
        this._toFrontendQueue = null;
        this._fromFrontendQueue = null;
        this._toBackendQueue = null;
        this._fromBackendQueue = null;
        
        // Bind methods to maintain 'this' context
        this.setQueues = this.setQueues.bind(this);
        this.connect = this.connect.bind(this);
        this.sendMessage = this.sendMessage.bind(this);
    }

    // Method to set the queue instances
    setQueues({ toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue }) {
        this._toFrontendQueue = toFrontendQueue;
        this._fromFrontendQueue = fromFrontendQueue;
        this._toBackendQueue = toBackendQueue;
        this._fromBackendQueue = fromBackendQueue;
        console.log('WebSocketManager: Queues set via setQueues method.');
        return this; // Allow method chaining
    }

    connect(url = 'ws://localhost:8000/ws') {
        console.group('WebSocketManager: Connect');
        
        // Clear any pending reconnection attempt
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        console.log(`Attempting to connect to WebSocket at ${url}...`);
        
        // Close existing connection if it exists
        if (this.ws) {
            this.ws.onclose = null; // Remove previous handler to prevent recursive reconnects
            this.ws.close();
        }

        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            console.log('WebSocket already open or connecting.');
            console.groupEnd();
            return;
        }

        this.ws = new WebSocket(url);

        this.ws.onopen = (event) => {
            console.log('WebSocket OPEN event received:', event);
            this.reconnectAttempts = 0; // Reset reconnect attempts on successful connection
            document.getElementById('connectionStatus').textContent = 'Connected';
            document.getElementById('connectionStatus').style.color = 'green';
            // Send an acknowledgement to the backend that frontend is ready
            this.sendMessage({ type: 'frontend_ready_ack', data: { message: 'Frontend ready to receive'} });
            // Dispatch a custom event to notify other modules (like EventListeners)
            // that the WebSocket is now ready and acknowledged.
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
                this.handleIncomingMessage(message);
                // Trigger message processing after enqueuing
                processBackendMessages();
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e, event.data);
                const errorElement = document.getElementById('wsErrors');
                if (errorElement) {
                    errorElement.textContent = `WebSocket error: ${e.message}`;
                }
            }
        };

        this.ws.onclose = (event) => {
            console.warn('WebSocket CLOSE event received:', event);
            document.getElementById('connectionStatus').textContent = 'Disconnected';
            document.getElementById('connectionStatus').style.color = 'red';

            // Only reconnect if the close was unexpected
            if (!event.wasClean || event.code !== 1000) {
                this.reconnectAttempts++;
                const baseDelay = 1000;
                const maxDelay = 30000;
                const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts), maxDelay);
                
                console.log(`Attempting to reconnect in ${delay / 1000} seconds... (Attempt ${this.reconnectAttempts})`);
                
                this.reconnectTimer = setTimeout(() => {
                    console.log('Executing reconnect attempt...');
                    this.connect(url);
                }, delay);
            } else {
                console.log('WebSocket closed intentionally, not reconnecting');
            }
            console.groupEnd();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket ERROR event received:', error);
            document.getElementById('connectionStatus').textContent = 'Error';
            document.getElementById('connectionStatus').style.color = 'orange';
            console.groupEnd();
        };
    }

    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('Sending message:', message);
            this._toBackendQueue.enqueue(message); // Enqueue for backend processing
            // WebSocketManager itself can directly send or have a separate sender task
            // For now, let's assume it directly sends. If you have a QueueForwarder,
            // this part would differ.
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not open. Message not sent:', message);
            // Optionally enqueue to fromFrontendQueue if you want to retry sending
            // this._fromFrontendQueue.enqueue(message);
        }
    }

    handleIncomingMessage(message) {
        console.log('Handling incoming message:', message);
        this._fromBackendQueue.enqueue(message); // Messages from backend go to fromBackendQueue
        // The MessageProcessor in EventListeners.js will dequeue and process this.
    }

    checkConnection() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.log('WebSocket connection lost, attempting to reconnect...');
            this.connect();
            return false;
        }
        return true;
    }
};

// Export the class
export default WebSocketManager;
