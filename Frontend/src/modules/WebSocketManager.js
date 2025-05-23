// WebSocketManager.js
import { fromBackendQueue, toBackendQueue, toFrontendQueue } from './MessageQueue.js';
import { updateQueueDisplay } from './QueueDisplay.js'; // Needed to trigger display after processing

// This is where 'lastMessage' was used. We need to pass it or make it accessible.
// For now, let's create a local variable and expose a way to get the last message if needed.
let _lastReceivedMessage = null;

const WebSocketManager = {
    ws: null,
    reconnectAttempts: 0,
    MAX_RECONNECT_ATTEMPTS: 5,
    RECONNECT_DELAY: 1000,
    isConnected: false,
    pingInterval: null,
    _wsReadyState: WebSocket.CLOSED,

    handleIncomingMessage: function(event) {
        try {
            const startTime = performance.now();
            const data = JSON.parse(event.data);
            console.log('Raw message data:', event.data);
            console.log('Parsed message:', data);
            console.log(`Message processing started at ${startTime.toFixed(2)}ms`);

            _lastReceivedMessage = data; // Update last received message

            if (data.type === "connection_ack") {
                console.log('WebSocket connection acknowledged by server');
                WebSocketManager.isConnected = true;
                document.dispatchEvent(new CustomEvent('websocket-ack', { detail: data }));
                return;
            } else if (data.type === "pong") {
                console.log('Received pong response from server');
                document.dispatchEvent(new CustomEvent('websocket-pong', { detail: data }));
                return;
            } else if (data.type === "error") {
                console.error(`Backend Error: ${data.message}`, data.details || '');
                fromBackendQueue.enqueue({
                    ...data,
                    _debug: {
                        received: Date.now(),
                        queue: 'fromBackend'
                    }
                });
            } else if (data.type === "status_update" ||
                       data.type === "sys_init" ||
                       data.type === "simulation_update") {
                console.groupCollapsed(`Handling backend message [${data.type}]`);
                console.log('Raw message:', data);
                debugger; // Pause vor enqueue
                const queuedMessage = {
                    ...data,
                    _debug: {
                        received: Date.now(),
                        queue: 'fromBackend'
                    }
                });
                console.log('Added to fromBackendQueue');
                // debugger; // Keep this debugger for now for simulation_update flow
                console.log("DEBUG: fromBackendQueue size after WebSocket receipt:", fromBackendQueue.size(), "Content:", fromBackendQueue.queue);
                console.groupEnd();
            } else if (data.type === "frontend_message") {
                if (data && typeof data === 'object' && 'type' in data && 'data' in data && 'timestamp' in data) {
                    toFrontendQueue.enqueue(data);
                    console.log('Added to toFrontendQueue:', data);
                } else {
                    console.warn('Malformed message received for toFrontendQueue:', data);
                }
            } else if (data.type === "backend_message") {
                toBackendQueue.enqueue(data);
                console.log('Added to toBackendQueue:', data);
            } else if (data.type === "processed_message") {
                fromBackendQueue.enqueue(data);
                console.log('Added to fromBackendQueue:', data);
            }
            // The simulation_update specific handling was moved into the above block.
            // If there are other specific simulation_update paths, they should be here too.
            // else if (data.type === "simulation_update") {
            //    fromBackendQueue.enqueue(data);
            //    console.log('Added to fromBackendQueue (simulation):', data);
            // }
            else {
                console.log('Unhandled message type:', data.type, data);
            }

            console.log("DEBUG: Message processing complete in handleIncomingMessage");
        } catch (e) {
            console.error('Error processing message:', e);
        }
    },

    connect() {
        console.group('WebSocketManager.connect()');
        console.log('Starting WebSocket connection process...');
        
        // Update UI status immediately
        const statusElement = document.getElementById('connectionStatus');
        if (statusElement) {
            statusElement.textContent = 'Connecting...';
            statusElement.style.color = 'orange';
            statusElement.style.fontWeight = 'bold';
        }

        if (this.ws) {
            console.log('Existing WebSocket found, cleaning up...');
            this.ws.onopen = null;
            this.ws.onclose = null;
            this.ws.onerror = null;
            const oldState = this.ws.readyState;
            if (oldState === WebSocket.OPEN || oldState === WebSocket.CONNECTING) {
                console.log(`Closing existing WebSocket (state: ${oldState})...`);
                this.ws.close();
            }
            if (this.pingInterval) {
                console.log('Clearing existing ping interval...');
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }
        }

        console.log('Creating new WebSocket instance...');
        this.ws = new WebSocket('ws://localhost:8000/ws');
        console.log(`WebSocket created, readyState: ${this.ws.readyState} (${this.getStateName(this.ws.readyState)})`);

        console.log('Setting up message handler...');
        this.ws.onmessage = (event) => {
            console.groupCollapsed(`Received WebSocket message (size: ${event.data.length} bytes)`);
            this.handleIncomingMessage(event);
            console.groupEnd();
        };
        console.log('WebSocket message handler configured');

        this._wsReadyState = this.ws.readyState;
        this.isConnected = this.ws.readyState === WebSocket.OPEN;

        this.ws.onopen = () => {
            console.log('WebSocket OPEN event received');
            this._wsReadyState = WebSocket.OPEN;
            this.isConnected = true;
            this.reconnectAttempts = 0;

            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

            const ackListener = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'connection_ack') {
                        console.log('Backend acknowledged connection.');
                        this.isConnected = true;
                        this.ws.removeEventListener('message', ackListener);

                        console.log('Starting regular ping interval...');
                        this.pingInterval = setInterval(() => {
                            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                                this.send({ type: 'ping', data: {}, timestamp: Date.now() });
                            } else {
                                clearInterval(this.pingInterval);
                                this.pingInterval = null;
                                console.warn('Ping interval cleared: WebSocket not open.');
                            }
                        }, 30000);

                        document.dispatchEvent(new CustomEvent('websocket-ready'));
                    }
                } catch (e) {
                    console.error('Error processing ACK message:', e);
                }
            };
            this.ws.addEventListener('message', ackListener);

            console.log('Waiting for backend connection acknowledgment...');
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event);
            this._wsReadyState = WebSocket.CLOSED;
            this.isConnected = false;
            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

            if (event.code !== 1000 && this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
                const delay = Math.min(this.RECONNECT_DELAY * (this.reconnectAttempts + 1), 5000);
                console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.MAX_RECONNECT_ATTEMPTS})...`);
                setTimeout(() => this.connect(), delay);
                this.reconnectAttempts++;
            } else if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
                console.warn('Max reconnect attempts reached. Not attempting to reconnect.');
            }
        };

        this.ws.onerror = (error) => {
            console.group('WebSocket ERROR Event');
            console.error('WebSocket connection error:', error);
            console.log('ReadyState:', this.getStateName(this.ws.readyState));
            console.groupEnd();
            
            this._wsReadyState = WebSocket.CLOSED;
            this.isConnected = false;
            
            // Update UI status
            const statusElement = document.getElementById('connectionStatus');
            if (statusElement) {
                statusElement.textContent = 'Connection Error';
                statusElement.style.color = 'red';
            }

            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }
        };
    },

    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
            return true;
        }
        console.warn('WebSocket not ready, message not sent:', message);
        return false;
    },

    getStateName(state) {
        const states = {
            0: 'CONNECTING',
            1: 'OPEN',
            2: 'CLOSING',
            3: 'CLOSED'
        };
        return states[state] || 'UNKNOWN';
    },

    getState() {
        if (!this.ws) return WebSocket.CLOSED;
        return this.ws.readyState;
    },
    getLastReceivedMessage: function() { // Expose a way to get the last message for QueueDisplay or other modules
        return _lastReceivedMessage;
    }
};

export { WebSocketManager };
