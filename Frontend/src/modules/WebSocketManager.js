// frontend/src/modules/WebSocketManager.js

import { fromBackendQueue, toBackendQueue, fromFrontendQueue, toFrontendQueue } from '../app.js'; // Import the queues
import { processBackendMessages } from './EventListeners.js'; // Import the message processor

const WebSocketManager = {
    ws: null,
    reconnectAttempts: 0,
    // Add these properties to hold the queue instances
    _toFrontendQueue: null,
    _fromFrontendQueue: null,
    _toBackendQueue: null,
    _fromBackendQueue: null,

    // Method to set the queue instances
    setQueues({ toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue }) {
        this._toFrontendQueue = toFrontendQueue;
        this._fromFrontendQueue = fromFrontendQueue;
        this._toBackendQueue = toBackendQueue;
        this._fromBackendQueue = fromBackendQueue;
        console.log('WebSocketManager: Queues set.');
    },

    connect(url = 'ws://localhost:8000/ws') {
        console.group('WebSocketManager: Connect');
        console.log(`Attempting to connect to WebSocket at ${url}...`);
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
            // Implement reconnect logic
            if (event.code !== 1000 && event.code !== 1001) { // 1000 = Normal Closure, 1001 = Going Away
                this.reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000); // Max 30 seconds
                console.log(`Attempting to reconnect in ${delay / 1000} seconds... (Attempt ${this.reconnectAttempts})`);
                setTimeout(() => this.connect(url), delay);
            }
            console.groupEnd();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket ERROR event received:', error);
            document.getElementById('connectionStatus').textContent = 'Error';
            document.getElementById('connectionStatus').style.color = 'orange';
            console.groupEnd();
        };
    },

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
    },

    handleIncomingMessage(message) {
        console.log('Handling incoming message:', message);
        this._fromBackendQueue.enqueue(message); // Messages from backend go to fromBackendQueue
        // The MessageProcessor in EventListeners.js will dequeue and process this.
    }
};

export { WebSocketManager };
