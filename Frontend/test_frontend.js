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

// Initialize queues
const toBackendQueue = new MessageQueue();
const fromBackendQueue = new MessageQueue();

// WebSocket connection
let websocket = null;
let lastMessage = null;

function initWebSocket() {
    websocket = new WebSocket('ws://localhost:8000/ws');
    
    websocket.onopen = () => {
        console.log('WebSocket connection established');
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        lastMessage = data;
        fromBackendQueue.enqueue(data);
        updateQueueDisplay();
        console.log('Received from backend:', data);
    };

    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function updateQueueDisplay() {
    const display = document.getElementById('queueDisplay');
    if (display) {
        display.innerHTML = `
            <h3>Queue Status</h3>
            <p>To Backend: ${toBackendQueue.size()}</p>
            <p>From Backend: ${fromBackendQueue.size()}</p>
            <p>Last Message: ${lastMessage ? JSON.stringify(lastMessage) : 'None'}</p>
        `;
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
