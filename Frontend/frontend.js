// Initialize all queues
class MessageQueue {
    constructor() {
        this.queue = [];
        this.pending = [];
    }

    enqueue(message) {
        this.queue.push(message);
        while (this.pending.length > 0 && this.queue.length > 0) {
            const resolve = this.pending.shift();
            resolve(this.queue.shift());
        }
    }

    async dequeue() {
        if (this.queue.length > 0) {
            return this.queue.shift();
        }
        return new Promise(resolve => this.pending.push(resolve));
    }

    size() {
        return this.queue.length;
    }
}

const toBackendQueue = new MessageQueue();
const fromBackendQueue = new MessageQueue();
const toFrontendQueue = new MessageQueue();
const fromFrontendQueue = new MessageQueue();

let lastMessage = null;

const MAX_VISIBLE_ITEMS = 20;

function updateQueueDisplay() {
    // Update queue logs
    updateQueueLog('toFrontendLog', toFrontendQueue);
    updateQueueLog('fromFrontendLog', fromFrontendQueue);
    updateQueueLog('toBackendLog', toBackendQueue);
    updateQueueLog('fromBackendLog', fromBackendQueue);
}

function updateQueueLog(logId, queue) {
    const logElement = document.getElementById(logId);
    if (!logElement) return;

    const items = queue.queue.slice().reverse();
    const now = Date.now();

    // Only show last 20 items to prevent overflow
    const visibleItems = items.slice(0, MAX_VISIBLE_ITEMS);

    logElement.innerHTML = visibleItems.map(item => {
        const timeDiff = (now - (item.timestamp * 1000)) / 1000;
        let statusClass = '';
        let content = '';

        if (item.data && item.data.id) {
            if (item.status === 'created') statusClass = 'status-created';
            if (item.status === 'processing') statusClass = 'status-processing';
            if (item.status === 'processed') statusClass = 'status-processed';
            content = `${item.data.id}: ${item.data.data}<br>
                      <small>${item.status?.toUpperCase() || ''} ${timeDiff.toFixed(1)}s ago</small>`;
        } else {
            content = `${item.type || 'message'}: ${JSON.stringify(item.data || item)}<br>
                      <small>${timeDiff.toFixed(1)}s ago</small>`;
        }

        return `<div class="log-entry ${statusClass}">${content}</div>`;
    }).join('');

    // Auto-scroll to bottom
    logElement.scrollTop = logElement.scrollHeight;

    // Add overflow indicator if there are more items
    if (queue.size() > MAX_VISIBLE_ITEMS) {
        logElement.innerHTML += `<div class="log-overflow">+${queue.size() - MAX_VISIBLE_ITEMS} more items</div>`;
    }
}

async function startSimulation() {
    try {
        console.log('Starting simulation...');

        // Clear all queues first
        toFrontendQueue.queue = [];
        fromFrontendQueue.queue = [];
        toBackendQueue.queue = [];
        fromBackendQueue.queue = [];

        updateQueueDisplay();

        const response = await fetch('http://localhost:8000/simulation/start', {
            mode: 'cors',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Simulation started:', result);

        // Send a test message through the WebSocket to notify the backend that the simulation has started.
        if (WebSocketManager.isConnected && WebSocketManager.getState() === WebSocket.OPEN) {
            WebSocketManager.send({
                messageContent: "Simulation started from frontend",
                message: "Simulation started from frontend",
                timestamp: Date.now()
            });
        } else {
            console.warn('WebSocket is not ready. Message not sent.');
        }
    } catch (error) {
        console.error('Failed to start simulation:', error);
        alert(`Failed to start simulation: ${error.message}`);
    }
}

async function stopSimulation() {
    try {
        const response = await fetch('http://localhost:8000/simulation/stop');
        console.log('Simulation stopped:', await response.json());
    } catch (error) {
        console.error('Failed to stop simulation:', error);
    }
}

// WebSocket connection manager
const WebSocketManager = {
    ws: null,
    reconnectAttempts: 0,
    MAX_RECONNECT_ATTEMPTS: 5,
    RECONNECT_DELAY: 1000,
    isConnected: false,
    pingInterval: null,
    _wsReadyState: WebSocket.CLOSED, // Internal state tracking

    // Define the WebSocket message handler function *outside* or *inside* connect,
    // but ensure it's a properly declared function that can be assigned.
    // Defining it as a method on WebSocketManager is a clean way to do it.
    handleIncomingMessage: function(event) {
        try {
            const startTime = performance.now();
            const data = JSON.parse(event.data);
            console.log('Raw message data:', event.data);
            console.log('Parsed message:', data);
            console.log(`Message processing started at ${startTime.toFixed(2)}ms`);

            lastMessage = data; // Update last received message

            // Handle system messages first
            if (data.type === "connection_ack") {
                console.log('WebSocket connection acknowledged by server');
                WebSocketManager.isConnected = true;
                document.dispatchEvent(new CustomEvent('websocket-ack', { detail: data }));
                return; // Now valid because it's inside the handleIncomingMessage function
            } else if (data.type === "pong") {
                console.log('Received pong response from server');
                document.dispatchEvent(new CustomEvent('websocket-pong', { detail: data }));
                return; // Valid here too
            }

            // Route application messages to appropriate queue
            if (data.type === "frontend_message") {
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
            } else if (data.type === "simulation_update") {
                fromBackendQueue.enqueue(data);
                console.log('Added to fromBackendQueue (simulation):', data);
            } else {
                console.log('Unhandled message type:', data.type, data);
            }

            updateQueueDisplay();
        } catch (e) {
            console.error('Error processing message:', e);
        }
    },


    connect() {
        console.group('WebSocketManager.connect()');
        console.log('Starting WebSocket connection process...');
        
        if (this.ws) {
            console.log('Existing WebSocket found, cleaning up...');
            // Clean up existing connection to prevent multiple connections
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

        // Assign the handler here!
        console.log('Setting up message handler...');
        this.ws.onmessage = (event) => {
            console.groupCollapsed(`Received WebSocket message (size: ${event.data.length} bytes)`);
            this.handleIncomingMessage(event);
            console.groupEnd();
        };
        console.log('WebSocket message handler configured');

        // Update internal readyState and isConnected property
        this._wsReadyState = this.ws.readyState;
        this.isConnected = this.ws.readyState === WebSocket.OPEN;

        this.ws.onopen = () => {
            console.log('WebSocket OPEN event received');
            this._wsReadyState = WebSocket.OPEN;
            this.isConnected = true;
            console.log('WebSocket connection established, readyState:', this.getState());
            this.reconnectAttempts = 0;

            // Verify connection with immediate ping
            const pingId = Date.now();
            this.send({ type: 'ping', timestamp: pingId });

            // Setup a one-time ping response handler to confirm connection
            const pingVerificationHandler = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'pong' && msg.timestamp === pingId) {
                        console.log('WebSocket connection verified with pong');
                        this.ws.removeEventListener('message', pingVerificationHandler); // Remove this specific handler
                        document.dispatchEvent(new CustomEvent('websocket-ready'));

                        // Start periodic ping only after initial verification
                        if (this.pingInterval) {
                            clearInterval(this.pingInterval);
                        }
                        this.pingInterval = setInterval(() => {
                            this.send({ type: 'ping', timestamp: Date.now() });
                        }, 30000); // Ping every 30 seconds
                    }
                } catch (e) {
                    console.error('Ping verification error:', e);
                }
            };
            this.ws.addEventListener('message', pingVerificationHandler);
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event);
            this._wsReadyState = WebSocket.CLOSED;
            this.isConnected = false;
            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

            if (event.code !== 1000 && this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) { // Code 1000 means normal closure
                const delay = Math.min(this.RECONNECT_DELAY * (this.reconnectAttempts + 1), 5000);
                console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.MAX_RECONNECT_ATTEMPTS})...`);
                setTimeout(() => this.connect(), delay);
                this.reconnectAttempts++;
            } else if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
                console.warn('Max reconnect attempts reached. Not attempting to reconnect.');
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this._wsReadyState = WebSocket.CLOSED;
            this.isConnected = false;
            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }
            // Error typically leads to a close event, so reconnect logic is primarily in onclose
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
    }
};

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.group('DOMContentLoaded');
    console.log('Initializing frontend...');
    
    // Setup button handlers
    console.log('Setting up button handlers...');
    document.getElementById('startSim').addEventListener('click', startSimulation);
    document.getElementById('stopSim').addEventListener('click', stopSimulation);
    console.log('Button handlers configured');

    // Initialize WebSocket connection
    console.log('Initializing WebSocket connection...');
    WebSocketManager.connect();
    
    // Monitor connection state changes
    document.addEventListener('websocket-ack', () => {
        console.log('WebSocket fully initialized and acknowledged by server');
        document.getElementById('connectionStatus').textContent = 'Connected';
        document.getElementById('connectionStatus').style.color = 'green';
    });
    
    console.groupEnd();

    // The display is updated on each message arrival, no need for a separate interval
});
