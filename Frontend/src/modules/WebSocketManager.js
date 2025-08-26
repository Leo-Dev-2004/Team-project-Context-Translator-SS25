// frontend/src/modules/WebSocketManager.js (FINALIZED with ALL debugging logs)

console.log('--- WebSocketManager.js file is being parsed ---'); // <<< CRUCIAL LOG: ADDED AT THE VERY TOP

// Make sure you have this import if updateQueueDisplay is used in _onMessage
// You might need to adjust the path if QueueDisplay.js is not in the same directory
import { updateQueueDisplay } from './QueueDisplay.js';

const DEFAULT_WEBSOCKET_URL = 'ws://127.0.0.1:8000/ws'; // Default URL for backend WebSocket

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // 1 second
        this.queues = {};
        this.observer = null; // For external logging/observers
        this.clientId = null; // Client ID for this session
        console.log('WebSocketManager: Constructor called.'); // LOG: Constructor called
    }

    setClientId(clientId) {
        this.clientId = clientId;
        console.log('WebSocketManager: Client ID set to:', this.clientId); // LOG: Client ID set
    }

    setQueues(queues) {
        this.queues = queues;
        console.log('WebSocketManager: Queues set:', Object.keys(queues)); // LOG: Queues set
        
        // IMPORTANT: Subscribe to the queues so their changes update the display
        if (this.queues.toBackendQueue) {
            this.queues.toBackendQueue.subscribe((queueName, size, items) => {
                updateQueueDisplay(queueName, size, items);
            });
        }
        if (this.queues.fromBackendQueue) {
            this.queues.fromBackendQueue.subscribe((queueName, size, items) => {
                updateQueueDisplay(queueName, size, items);
            });
        }

        // Start the loop to send messages from the outgoing queue
        this._startSendingOutgoingMessages();
    }

    setObserver(observer) {
        this.observer = observer;
        console.log('WebSocketManager: Observer set.'); // LOG: Observer set
    }

    connect(url = DEFAULT_WEBSOCKET_URL) {
        if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.warn('WebSocketManager: Already connected. Skipping new connection attempt.');
            return;
        }

        console.log(`WebSocketManager: Attempting to connect to ${url}... (Attempt ${this.reconnectAttempts + 1})`); // LOG: Connection attempt

        // Append client ID to the WebSocket URL
        const connectionUrl = this.clientId ? `${url}?client_id=${this.clientId}` : url;
        
        try {
            this.ws = new WebSocket(connectionUrl);
            this.ws.onopen = this._onOpen.bind(this);
            this.ws.onmessage = this._onMessage.bind(this);
            this.ws.onclose = this._onClose.bind(this);
            this.ws.onerror = this._onError.bind(this);
            console.log('WebSocketManager: WebSocket object created.'); // LOG: WebSocket object created
        } catch (error) {
            console.error('WebSocketManager: Error creating WebSocket object:', error); // LOG: Error creating WebSocket
            this._scheduleReconnect();
        }
    }

    _onOpen() {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        console.log('WebSocketManager: Connection established (_onOpen)!'); // LOG: Connection established
        this._updateConnectionStatus(); // Update UI
        // Send a ready_ack message immediately after connection is established
        const readyAckMessage = {
            id: crypto.randomUUID(),
            type: 'frontend.ready_ack',
            payload: { message: 'Frontend is ready to receive messages.' },
            timestamp: Date.now() / 1000,
            client_id: this.clientId,
            origin: 'frontend',
            destination: 'backend'
        };
        // Enqueue to the outbound queue, which this manager will then send.
        if (this.queues.toBackendQueue) {
            this.queues.toBackendQueue.enqueue(readyAckMessage);
            console.log('WebSocketManager: Enqueued ready_ack message:', readyAckMessage.type);
        } else {
            console.error('WebSocketManager: toBackendQueue is not set. Cannot send ready_ack.');
        }
    }

    _onMessage(event) {
        console.log('WebSocketManager: Raw message received.', event.data); // LOG: Raw data
        this._updateConnectionStatus(); // Update UI if needed

        try {
            const message = JSON.parse(event.data);
            console.log('WebSocketManager: Parsed message:', message); // LOG: Parsed message

            // Ensure message has a 'type' property
            if (!message || typeof message.type === 'undefined') {
                console.warn('WebSocketManager: Received message without a "type" property:', message);
                return;
            }

            // Route messages to specific queues based on their type or intended destination
            switch (message.type) {
                case 'stt.transcription':
                    console.debug("WebSocketManager: TRANSCRIPTION RECEIVED!!!! ERFOLG!"); // LOG: Transcription received
                    this.queues.fromBackendQueue.enqueue(message);
                    break;

                case 'tts.speak':
                    console.debug("WebSocketManager: TTS SPEAK message received."); // LOG: TTS Speak received
                    this.queues.fromBackendQueue.enqueue(message);
                    break;

                case 'system.queue_status_update':
                    console.debug("WebSocketManager: Queue status update received."); // LOG: Queue status update received
                    if (message.payload) {
                        // The backend sends the queue names as 'from_frontend_q_size', 'to_frontend_q_size', 'dead_letter_q_size' in payload
                        // Make sure these match EXACTLY with what the backend sends.
                        updateQueueDisplay('from_frontend_queue', message.payload.from_frontend_q_size, []);
                        updateQueueDisplay('to_frontend_queue', message.payload.to_frontend_q_size, []);
                        updateQueueDisplay('dead_letter_queue', message.payload.dead_letter_q_size, []);
                    }
                    break;

                default:
                    console.warn(`WebSocketManager: Unhandled message type: ${message.type}`, message); // LOG: Unhandled message type
                    this.queues.fromBackendQueue.enqueue(message); // Still enqueue unhandled messages for general processing
                    break;
            }

            if (this.observer && typeof this.observer.onMessage === 'function') {
                this.observer.onMessage(message);
            }

        } catch (error) {
            console.error('WebSocketManager: Error parsing or handling message:', error, 'Raw data:', event.data); // LOG: Error parsing/handling
            if (this.observer && typeof this.observer.onError === 'function') {
                this.observer.onError(error, event.data);
            }
        }
    }

    _onClose(event) {
        this.isConnected = false;
        console.log(`WebSocketManager: Connection closed. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`); // LOG: Connection closed
        this._updateConnectionStatus(); // Update UI
        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this._scheduleReconnect();
        } else if (!event.wasClean) {
            console.error('WebSocketManager: Max reconnect attempts reached. Not attempting to reconnect.'); // LOG: Max reconnects
        }
    }

    _onError(error) {
        console.error('WebSocketManager: WebSocket error:', error); // LOG: WebSocket error
        this.isConnected = false;
        this._updateConnectionStatus(); // Update UI
        // Force close to trigger _onClose and potential reconnect (if not clean)
        if (this.ws) { // Check if ws object exists before calling close
            this.ws.close();
        }
    }

    _scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
            console.log(`WebSocketManager: Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay / 1000} seconds...`); // LOG: Scheduling reconnect
            setTimeout(() => this.connect(), delay);
        }
    }

    _updateConnectionStatus() {
        console.log('WebSocketManager: Connection status updated:', this.isConnected ? 'CONNECTED' : 'DISCONNECTED'); // LOG: Connection status updated
    }

    _startSendingOutgoingMessages() {
        console.log('WebSocketManager: Starting to send outgoing messages...'); // LOG: Starting outgoing messages
        // Implement logic to dequeue from toBackendQueue and send
        // This loop ensures messages are sent when the WebSocket is open
        if (this.queues.toBackendQueue) {
            this.queues.toBackendQueue.subscribe(async (queueName, size, items) => {
                // When a message is enqueued, attempt to send it
                if (items.length > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const message = await this.queues.toBackendQueue.dequeue(); // Dequeue the message
                    if (message) { // Ensure message exists after dequeue
                        try {
                            this.ws.send(JSON.stringify(message));
                            console.log('WebSocketManager: Sent message to backend:', message.type);
                        } catch (error) {
                            console.error('WebSocketManager: Error sending message:', error);
                            // Re-enqueue if send failed due to temporary issue
                            this.queues.toBackendQueue.enqueue(message);
                        }
                    }
                }
            });
        } else {
            console.warn('WebSocketManager: toBackendQueue is not set for outgoing messages.');
        }
    }

    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocketManager: Sending message:', message.type); // LOG: Sending message
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocketManager: WebSocket is not open. Message not sent:', message.type); // LOG: Message not sent
            // Optionally, queue message for sending once connected
            if (this.queues.toBackendQueue) {
                this.queues.toBackendQueue.enqueue(message);
                console.log('WebSocketManager: Message enqueued for later sending:', message.type);
            }
        }
    }

    close() {
        if (this.ws) {
            console.log('WebSocketManager: Closing WebSocket connection intentionally.'); // LOG: Closing connection
            this.ws.close(1000, 'Client disconnected'); // 1000 is for normal closure
        }
    }
}

// Singleton pattern
export const WebSocketManager = new WebSocketManager();
console.log('--- WebSocketManager singleton instance exported ---'); // <<< CRUCIAL LOG: ADDED AT THE VERY END