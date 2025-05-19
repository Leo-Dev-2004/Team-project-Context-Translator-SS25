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

function initWebSocket() {
    websocket = new WebSocket('ws://localhost:8000/ws');
    
    websocket.onopen = () => {
        console.log('WebSocket connection established');
        // Request initial status
        websocket.send(JSON.stringify({type: "status_request"}));
    };

    websocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Received from backend:', data);
            
            lastMessage = data;
            
            // Route message to appropriate queue
            if (data.type === "simulation_update") {
                fromBackendQueue.enqueue(data);
                console.log("New simulation entry:", data.data);
            } else if (data.type === "frontend_message") {
                toFrontendQueue.enqueue(data);
            }
            
            // Update all queue displays
            updateQueueDisplay();
        } catch (e) {
            console.error('Error processing message:', e);
        }
    };

    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
        console.log('WebSocket disconnected - attempting to reconnect...');
        setTimeout(initWebSocket, 1000);
    };
}

const MAX_LOG_LINES = 50;
const MAX_LOG_HEIGHT = 350; // pixels

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
    
    logElement.innerHTML = items.map(item => {
        const timeDiff = ((now - (item.timestamp * 1000)) / 1000;
        let statusClass = '';
        
        if (item.status === 'created') statusClass = 'status-created';
        if (item.status === 'processing') statusClass = 'status-processing';
        if (item.status === 'processed') statusClass = 'status-processed';
        
        return `
            <div class="log-entry ${statusClass}">
                ${item.data.id}: ${item.data.data}<br>
                <small>${item.status.toUpperCase()} ${timeDiff.toFixed(1)}s ago</small>
            </div>
        `;
    }).join('');
    
    // Auto-scroll to bottom
    logElement.scrollTop = logElement.scrollHeight;
    
    if (logElement.scrollHeight > MAX_LOG_HEIGHT) {
        const overflow = document.createElement('div');
        overflow.className = 'log-overflow';
        overflow.textContent = 'QUEUE OVERFLOW - STOPPING SIMULATION';
        logElement.appendChild(overflow);
        stopSimulation();
    }
}

async function startSimulation() {
    try {
        const response = await fetch('http://localhost:8000/simulation/start');
        console.log('Simulation started:', await response.json());
    } catch (error) {
        console.error('Failed to start simulation:', error);
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

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    
    document.getElementById('startSim').addEventListener('click', startSimulation);
    document.getElementById('stopSim').addEventListener('click', stopSimulation);
    
    // Update display every second
    setInterval(updateQueueDisplay, 1000);
});
