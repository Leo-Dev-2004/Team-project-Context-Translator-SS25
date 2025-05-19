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
        // Request initial status
        websocket.send(JSON.stringify({type: "status_request"}));
    };

    websocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Received from backend:', data);
            
            lastMessage = data;
            fromBackendQueue.enqueue(data);
            
            // Update UI immediately
            updateQueueDisplay();
            
            // If this is a simulation update, show more details
            if (data.type === "simulation_update") {
                console.log("New simulation entry:", data.data);
            }
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

function updateQueueDisplay() {
    const display = document.getElementById('queueDisplay');
    if (display) {
        let messagePreview = 'None';
        if (lastMessage) {
            if (lastMessage.type === "simulation_update") {
                messagePreview = `Entry ${lastMessage.data.id}: ${lastMessage.data.data}`;
            } else {
                messagePreview = JSON.stringify(lastMessage);
            }
        }

        display.innerHTML = `
            <h3>Queue Status</h3>
            <p>To Backend: ${toBackendQueue.size()}</p>
            <p>From Backend: ${fromBackendQueue.size()}</p>
            <div class="last-message">
                <h4>Last Message:</h4>
                <p>${messagePreview}</p>
                ${lastMessage?.data?.timestamp ? 
                    `<p>${new Date(lastMessage.data.timestamp * 1000).toLocaleTimeString()}</p>` : ''}
            </div>
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
