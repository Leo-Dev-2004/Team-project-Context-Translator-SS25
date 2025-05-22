// Initialize all queues
class MessageQueue {
    constructor() {
        this.queue = [];
        this.pending = [];
        this._listeners = new Set();
    }

    enqueue(message) {
        // Add timestamp if not present
        if (!message.timestamp) {
            message.timestamp = Date.now() / 1000;
        }

        this.queue.push(message);

        // Notify all listeners
        this._listeners.forEach(cb => cb(this.queue));

        // Resolve pending dequeues
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

    addListener(callback) {
        this._listeners.add(callback);
    }

    removeListener(callback) {
        this._listeners.delete(callback);
    }

    clear() {
        this.queue = [];
        this._listeners.forEach(cb => cb(this.queue));
    }
}

const toBackendQueue = new MessageQueue();
const fromBackendQueue = new MessageQueue();
const toFrontendQueue = new MessageQueue();
const fromFrontendQueue = new MessageQueue();

let lastMessage = null;

const MAX_VISIBLE_ITEMS = 20;

let lastUpdateTime = 0;
const UPDATE_THROTTLE_MS = 100;

function updateQueueDisplay() {
    const now = performance.now();
    if (now - lastUpdateTime < UPDATE_THROTTLE_MS) {
        requestAnimationFrame(updateQueueDisplay);
        return;
    }
    lastUpdateTime = now;

    // Batch updates using microtask queue
    Promise.resolve().then(() => {
        updateQueueLog('toFrontendLog', toFrontendQueue);
        updateQueueLog('fromFrontendLog', fromFrontendQueue);
        updateQueueLog('toBackendLog', toBackendQueue);
        updateQueueLog('fromBackendLog', fromBackendQueue);
        updateQueueCounters();
    });
}

function updateQueueLog(logId, queue) {
    const logElement = document.getElementById(logId);
    if (!logElement) return;

    // Create a stable copy of queue items
    const items = [...queue.queue].reverse();
    const now = Date.now();

    // Apply smart filtering based on queue type
    let visibleItems = items;
    if (logId === 'toFrontendLog') {
        // Prioritize error and status messages
        visibleItems = items.sort((a, b) => {
            if (a.type === 'error') return -1;
            if (b.type === 'error') return 1;
            if (a.type === 'status_update') return -1;
            if (b.type === 'status_update') return 1;
            return 0;
        });
    }

    // Limit display while keeping actual queue intact
    visibleItems = visibleItems.slice(0, MAX_VISIBLE_ITEMS);

    // CORRECTED: Use map to create an array of HTML strings, then join them
    const htmlContent = visibleItems.map(item => {
        const timeDiff = (now - (item.timestamp * 1000)) / 1000;
        let statusClass = '';
        let content = '';

        if (item.type === 'status_update') {
            statusClass = `status-${item.data.status || 'unknown'}`;
            content = `<span class="message-id">${item.data.original_id || 'N/A'}</span>:
                       ${item.data.status?.toUpperCase() || 'UNKNOWN'} (${item.data.progress}%)<br>
                       <small>${timeDiff.toFixed(1)}s ago</small>`;
        } else if (item.type === 'error') {
            statusClass = 'status-error';
            content = `<span class="message-id">ERROR</span>:
                       ${item.data.message || 'Unknown error'}<br>
                       ${item.data.details ? `<small>${item.data.details}</small><br>` : ''}
                       <small>${timeDiff.toFixed(1)}s ago</small>`;
        } else if (item.data && item.data.id) {
            const itemStatus = item.status || item.data?.status;
            if (itemStatus === 'created') statusClass = 'status-created';
            else if (itemStatus === 'processing') statusClass = 'status-processing';
            else if (itemStatus === 'processed') statusClass = 'status-processed';
            content = `<span class="message-id">${item.data.id}</span>: ${item.data.data || JSON.stringify(item.data)}<br>
                      <small>${(itemStatus?.toUpperCase() || '')} ${timeDiff.toFixed(1)}s ago</small>`;
        } else {
            content = `<span class="message-type">${item.type || 'message'}</span>:
                       ${JSON.stringify(item.data || item)}<br>
                       <small>${timeDiff.toFixed(1)}s ago</small>`;
        }

        return `<div class="log-entry ${statusClass}">${content}</div>`;
    }).join('');

    logElement.innerHTML = htmlContent;
    logElement.scrollTop = logElement.scrollHeight;

    if (queue.size() > MAX_VISIBLE_ITEMS) {
        logElement.innerHTML += `<div class="log-overflow">+${queue.size() - MAX_VISIBLE_ITEMS} more items</div>`;
    }
}

async function startSimulation() {
    try {
        console.log('Starting simulation...');

        // Clear all queues first (good practice for new sim run)
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

        // Wait for backend confirmation via WebSocket instead of sending another message
        if (WebSocketManager.isConnected && WebSocketManager.getState() === WebSocket.OPEN) {
            console.log("Waiting for backend confirmation via WebSocket...");
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
                return;
            } else if (data.type === "pong") {
                console.log('Received pong response from server');
                document.dispatchEvent(new CustomEvent('websocket-pong', { detail: data }));
                return;
            }
            // Handle error messages explicitly
            else if (data.type === "error") {
                console.error(`Backend Error: ${data.message}`, data.details || '');
                fromBackendQueue.enqueue({
                    ...data,
                    _debug: {
                        received: Date.now(),
                        queue: 'fromBackend'
                    }
                });
            }
            // Handle backend-originated messages
            else if (data.type === "status_update" ||
                    data.type === "sys_init" ||
                    data.type === "simulation_update") {
                console.groupCollapsed(`Handling backend message [${data.type}]`);
                console.log('Raw message:', data);
                // Messages FROM backend go to fromBackendQueue
                fromBackendQueue.enqueue({
                    ...data,
                    _debug: {
                        received: Date.now(),
                        queue: 'fromBackend'
                    }
                });
                console.log('Added to fromBackendQueue');
                console.groupEnd();
            }

            // Route application messages to appropriate queue
            else if (data.type === "frontend_message") { // Message from frontend, but probably processed and sent back to frontend
                if (data && typeof data === 'object' && 'type' in data && 'data' in data && 'timestamp' in data) {
                    toFrontendQueue.enqueue(data);
                    console.log('Added to toFrontendQueue:', data);
                } else {
                    console.warn('Malformed message received for toFrontendQueue:', data);
                }
            } else if (data.type === "backend_message") { // Messages originating from backend for frontend display
                toBackendQueue.enqueue(data); // This queue name sounds like it's data *to* the backend. Reconfirm if this is meant to be displayed from backend.
                console.log('Added to toBackendQueue:', data);
            } else if (data.type === "processed_message") { // Messages processed by backend and sent back to frontend
                fromBackendQueue.enqueue(data);
                console.log('Added to fromBackendQueue:', data);
            } else if (data.type === "simulation_update") { // Simulation-specific updates from backend
                fromBackendQueue.enqueue(data);
                console.log('Added to fromBackendQueue (simulation):', data);
            }
            else {
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

            // Clear any previous ping interval immediately on open
            if (this.pingInterval) {
                clearInterval(this.pingInterval);
                this.pingInterval = null;
            }

            // Instead of immediate ping, set up a listener for the backend's ACK
            const ackListener = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'connection_ack') {
                        console.log('Backend acknowledged connection.');
                        this.isConnected = true; // Redundant, but ensures consistency
                        this.ws.removeEventListener('message', ackListener); // Remove listener after ACK

                        // Now that we have ACKED, start the regular ping interval
                        console.log('Starting regular ping interval...');
                        this.pingInterval = setInterval(() => {
                            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                                this.send({ type: 'ping', data: {}, timestamp: Date.now() }); // <-- Added data: {}
                            } else {
                                // Connection is no longer open, clear interval and trigger reconnect if needed
                                clearInterval(this.pingInterval);
                                this.pingInterval = null;
                                console.warn('Ping interval cleared: WebSocket not open.');
                                // Consider triggering a reconnect here if not already handled by onclose
                            }
                        }, 30000); // Send ping every 30 seconds

                        document.dispatchEvent(new CustomEvent('websocket-ready')); // Signal frontend is ready
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
            console.error('WebSocket error:', error);
            this._wsReadyState = WebSocket.CLOSED;
            this.isConnected = false;
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

    // Setup queue listeners
    setupQueueListeners(); // Moved before WebSocketManager.connect() for logical flow

    // Initialize WebSocket connection
    console.log('Initializing WebSocket connection...');
    WebSocketManager.connect();

    // Monitor connection state changes
    document.addEventListener('websocket-ack', () => {
        console.log('WebSocket fully initialized and acknowledged by server');
        document.getElementById('connectionStatus').textContent = 'Connected';
        document.getElementById('connectionStatus').style.color = 'green';

        // Start processing backend messages now that connection is ready
        console.log("Starting backend message processor...");
        processBackendMessages();
    });

    console.groupEnd();
});

function updateQueueCounters() {
    document.getElementById('toFrontendCount').textContent = toFrontendQueue.size();
    document.getElementById('fromFrontendCount').textContent = fromFrontendQueue.size();
    document.getElementById('toBackendCount').textContent = toBackendQueue.size();
    document.getElementById('fromBackendCount').textContent = fromBackendQueue.size();

    // Add debug information
    if (console.debug) {
        console.debug('Queue Stats:', {
            toFrontend: toFrontendQueue.size(),
            fromFrontend: fromFrontendQueue.size(),
            toBackend: toBackendQueue.size(),
            fromBackend: fromBackendQueue.size(),
            lastMessage: lastMessage ? lastMessage.type : 'none'
        });
    }
}

// Initialize queue listeners
function setupQueueListeners() {
    [toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue].forEach(queue => {
        queue.addListener(() => updateQueueDisplay());
    });
}

// Frontend message processor
async function processBackendMessages() {
    console.log("processBackendMessages: Started loop.");
    while (true) {
        try {
            console.log("processBackendMessages: Waiting for message...");
        try {
            const message = await fromBackendQueue.dequeue();
            console.groupCollapsed(`Processing backend message [${message.type}]`);
            console.log('Raw message:', message);

            // Calculate processing time
            const processingStart = Date.now();
            const queueTime = processingStart - (message._debug?.received || processingStart);

            // Handle different message types
            let processedMessage = {...message};

            if (message.type === 'status_update') {
                processedMessage = {
                    ...message,
                    _debug: {
                        ...message._debug,
                        processed: true,
                        processingTime: Date.now() - processingStart,
                        queueTime: queueTime
                    }
                };
                toFrontendQueue.enqueue(processedMessage);
            }
            else if (message.type === 'sys_init') {
                console.log('System initialization received');
                // Additional initialization logic here
                toFrontendQueue.enqueue(processedMessage);
            }
            else if (message.type === 'simulation_update') {
                console.log('Simulation update received and enqueued for display');
                processedMessage = {
                    ...message,
                    _debug: {
                        ...message._debug,
                        processed: true,
                        processingTime: Date.now() - processingStart,
                        queueTime: queueTime
                    }
                };
                toFrontendQueue.enqueue(processedMessage);
            }

            updateQueueDisplay();
            console.log('Message processed in', Date.now() - processingStart, 'ms');
            console.groupEnd();
        } catch (error) {
            console.error('Error processing message:', error);
        }
    }
}
