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
    if (!logElement) {
        console.error('Queue log element not found:', logId);
        return;
    }

    try {
        const items = queue.queue.slice().reverse();
        const now = Date.now();

        logElement.innerHTML = items.slice(0, MAX_VISIBLE_ITEMS).map(item => {
            const timeDiff = (now - (item.timestamp * 1000)) / 1000;
            let statusClass = '';
            let content = '';

            // Handle different message types
            if (item.type === 'test_message') {
                statusClass = item.data?.status === 'processed' ? 'status-processed' : 'status-pending';
                content = `TEST: ${item.data?.content || 'No content'}<br>
                          <small>${item.data?.status?.toUpperCase() || 'PENDING'} ${timeDiff.toFixed(1)}s ago</small>`;
            } 
            else if (item.type === 'system') {
                statusClass = 'status-system';
                content = `SYSTEM: ${item.data?.message || 'No message'}<br>
                          <small>${timeDiff.toFixed(1)}s ago</small>`;
            }
            else if (item.type === 'simulation') {
                statusClass = item.data?.status === 'processed' ? 'status-processed' : 'status-processing';
                content = `SIM: ${item.data?.content || 'No content'}<br>
                          <small>${item.data?.status?.toUpperCase() || 'PROCESSING'} ${timeDiff.toFixed(1)}s ago</small>`;
            }
            else {
                statusClass = 'status-unknown';
                content = `${item.type || 'message'}: ${JSON.stringify(item.data || item)}<br>
                          <small>${timeDiff.toFixed(1)}s ago</small>`;
            }

            return `<div class="log-entry ${statusClass}">${content}</div>`;
        }).join('');

        if (queue.size() > MAX_VISIBLE_ITEMS) {
            logElement.innerHTML += `<div class="log-overflow">+${queue.size() - MAX_VISIBLE_ITEMS} more items</div>`;
        }

        logElement.scrollTop = logElement.scrollHeight;
    } catch (e) {
        console.error('Error updating queue log:', e);
        logElement.innerHTML = `<div class="log-error">Error displaying messages</div>`;
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

function sendTestMessage() {
    if (WebSocketManager.isConnected && WebSocketManager.getState() === WebSocket.OPEN) {
        const testMsg = {
            type: "test_message",
            data: {
                id: "test_" + Date.now(),
                content: "This is a test message",
                status: "pending",
                progress: 0
            },
            timestamp: Date.now() / 1000,
            processing_path: [],
            forwarding_path: []
        };
        
        console.log('Sending test message:', testMsg);
        WebSocketManager.send(JSON.stringify(testMsg));
        updateQueueDisplay();
    } else {
        console.warn('Cannot send test message - WebSocket not connected');
        alert('WebSocket not connected. Please wait for connection.');
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
            const data = JSON.parse(event.data);
            console.groupCollapsed('Received WebSocket message:', data.type);
            console.log('Full message:', data);
            
            lastMessage = data;

            // Handle connection messages
            if (data.type === "connection_ack") {
                console.log('Connection acknowledged');
                WebSocketManager.isConnected = true;
                document.dispatchEvent(new CustomEvent('websocket-ack', { detail: data }));
                console.groupEnd();
                return;
            }

            if (data.type === "pong") {
                console.log('Pong received');
                document.dispatchEvent(new CustomEvent('websocket-pong', { detail: data }));
                console.groupEnd();
                return;
            }

            // Route messages to appropriate queues
            switch(data.type) {
                case "system":
                case "simulation":
                case "status_update":
                    console.log('Adding to fromBackendQueue');
                    fromBackendQueue.enqueue(data);
                    break;
                    
                case "test_message":
                    console.log('Adding test message to fromFrontendQueue');
                    fromFrontendQueue.enqueue(data);
                    break;
                    
                case "error":
                    console.error('Server error:', data.data?.message);
                    break;
                    
                default:
                    console.warn('Unhandled message type:', data.type);
                    break;
            }

            updateQueueDisplay();
            console.groupEnd();
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

// Refresh queues periodically
function startQueueRefresh() {
    setInterval(() => {
        updateQueueDisplay();
    }, 500); // Update every 500ms
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    startQueueRefresh();
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
