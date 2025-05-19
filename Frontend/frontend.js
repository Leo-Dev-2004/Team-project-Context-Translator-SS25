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

// Initialize all queues
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
    const visibleItems = items.slice(0, 20);
    
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
    
    // Remove overflow check since we're limiting items
    if (queue.size() > 20) {
        logElement.innerHTML += `<div class="log-overflow">+${queue.size() - 20} more items</div>`;
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
        
        // Send test message through WebSocket manager
        WebSocketManager.send({
            type: "test", 
            message: "Simulation started from frontend",
            timestamp: Date.now()
        });
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

// WebSocket message handler
const handleWebSocketMessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        console.log('Received WebSocket message:', data);
        
        lastMessage = data;
        
        // Handle system messages first
        if (data.type === "connection_ack") {
            console.log('WebSocket connection acknowledged by server');
            WebSocketManager.isConnected = true;
            document.dispatchEvent(new CustomEvent('websocket-ack', { detail: data }));
            return;
        }
        else if (data.type === "pong") {
            console.log('Received pong response from server');
            document.dispatchEvent(new CustomEvent('websocket-pong', { detail: data }));
            return;
        }
        
        // Route application messages to appropriate queue
        if (data.type === "frontend_message") {
            toFrontendQueue.enqueue(data);
            console.log('Added to toFrontendQueue:', data);
        } 
        else if (data.type === "backend_message") {
            toBackendQueue.enqueue(data);
            console.log('Added to toBackendQueue:', data);
        }
        else if (data.type === "processed_message") {
            fromBackendQueue.enqueue(data);
            console.log('Added to fromBackendQueue:', data);
        }
        else if (data.type === "simulation_update") {
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
};

// WebSocket connection manager
const WebSocketManager = {
    ws: null,
    reconnectAttempts: 0,
    MAX_RECONNECT_ATTEMPTS: 5,
    RECONNECT_DELAY: 1000,
    isConnected: false,

    connect() {
        if (this.ws) {
            // Clean up existing connection
            this.ws.onopen = null;
            this.ws.onclose = null;
            this.ws.onerror = null;
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.close();
            }
        }

        this.ws = new WebSocket('ws://localhost:8000/ws');
        console.log('WebSocket created, readyState:', this.ws.readyState);

        // Clear any existing message handler first
        if (this.ws.onmessage) {
            this.ws.onmessage = null;
        }

        // Set up the new message handler
        this.ws.onmessage = handleWebSocketMessage;

        // Immediately update state
        this.isConnected = this.ws.readyState === WebSocket.OPEN;
        
        this.ws.onopen = () => {
            console.log('WebSocket OPEN event received');
            this._wsReadyState = WebSocket.OPEN;
            this.isConnected = true;
            console.log('WebSocket connection established, readyState:', this.getState());
            this.reconnectAttempts = 0;
            
            // Verify connection with immediate ping
            const pingId = Date.now();
            this.send({type: 'ping', timestamp: pingId});
            
            // Setup ping response handler
            const pingHandler = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'pong' && msg.timestamp === pingId) {
                        console.log('WebSocket connection verified with pong');
                        this.ws.removeEventListener('message', pingHandler);
                        document.dispatchEvent(new Event('websocket-ready'));
                        
                        // Start periodic ping
                        this.pingInterval = setInterval(() => {
                            this.send({type: 'ping', timestamp: Date.now()});
                        }, 30000);
                    }
                } catch (e) {
                    console.error('Ping verification error:', e);
                }
            };
            
            this.ws.addEventListener('message', pingHandler);
        };

        // Add state tracking
        Object.defineProperty(this.ws, 'readyState', {
            get: () => this._wsReadyState,
            set: (val) => {
                this._wsReadyState = val;
                this.isConnected = val === WebSocket.OPEN;
            }
        });

        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event);
            this.isConnected = false;
            if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
                const delay = Math.min(this.RECONNECT_DELAY * (this.reconnectAttempts + 1), 5000);
                console.log(`Reconnecting in ${delay}ms...`);
                setTimeout(() => this.connect(), delay);
                this.reconnectAttempts++;
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.isConnected = false;
        };
    },

    send(message) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
            return true;
        }
        console.warn('WebSocket not ready, message not sent');
        return false;
    },

    getState() {
        if (!this.ws) return WebSocket.CLOSED;
        // Force state update by checking underlying socket
        try {
            return this.ws.readyState;
        } catch (e) {
            return WebSocket.CLOSED;
        }
    }
};

// Initial connection
WebSocketManager.connect();

// Expose for debugging
window.wsManager = WebSocketManager;


//Frontend/frontend.js

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Setup button handlers
    document.getElementById('startSim').addEventListener('click', startSimulation);
    document.getElementById('stopSim').addEventListener('click', stopSimulation);
    
    // Update display immediately when messages arrive
    // No need for interval since we update on each message
});
