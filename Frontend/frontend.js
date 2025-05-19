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

// WebSocket connection
let websocket = null;
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
        
        // Ensure WebSocket is connected before sending
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "test",
                message: "Simulation started from frontend",
                timestamp: Date.now()
            }));
        } else {
            console.warn('WebSocket not ready, cannot send test message');
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

// Initialize WebSocket connection with retry logic
let ws = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8000/ws');
    console.log('WebSocket created, readyState:', ws.readyState);

    ws.onopen = () => {
        console.log('WebSocket connection established, readyState:', ws.readyState);
        reconnectAttempts = 0;
        document.dispatchEvent(new Event('websocket-ready'));
    };

    ws.onclose = (event) => {
        console.log('WebSocket closed:', event);
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            const delay = Math.min(1000 * (reconnectAttempts + 1), 5000);
            console.log(`Reconnecting in ${delay}ms...`);
            setTimeout(connectWebSocket, delay);
            reconnectAttempts++;
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// Initial connection
connectWebSocket();

ws.onerror = (error) => {
    console.error('WebSocket connection error:', error, 'readyState:', ws.readyState);
};

// Log WebSocket state changes
ws.addEventListener('open', () => console.log('WebSocket open, readyState:', ws.readyState));
ws.addEventListener('error', () => console.log('WebSocket error, readyState:', ws.readyState));
ws.addEventListener('close', () => console.log('WebSocket closed, readyState:', ws.readyState));

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Wait for WebSocket to be ready
    document.addEventListener('websocket-ready', () => {
    // Setup WebSocket handlers
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Received WebSocket message:', data);
            
            lastMessage = data;
            
            // Route message to appropriate queue
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
                // This is the main message type from backend
                fromBackendQueue.enqueue(data);
                console.log('Added to fromBackendQueue (simulation):', data);
            }
            else {
                console.log('Unknown message type:', data.type);
            }
            
            updateQueueDisplay();
        } catch (e) {
            console.error('Error processing message:', e);
        }
    };

    ws.onopen = () => {
        console.log('WebSocket connection established');
        updateQueueDisplay();
    };

    ws.onerror = (error) => {
        console.error('WebSocket connection failed:', error);
        // Attempt reconnection
        setTimeout(() => {
            window.ws = new WebSocket('ws://localhost:8000/ws');
        }, 1000);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected - attempting to reconnect...');
        setTimeout(() => {
            window.ws = new WebSocket('ws://localhost:8000/ws');
        }, 1000);
    };

    });

    // Setup button handlers
    document.getElementById('startSim').addEventListener('click', startSimulation);
    document.getElementById('stopSim').addEventListener('click', stopSimulation);
    
    // Update display immediately when messages arrive
    // No need for interval since we update on each message
});
