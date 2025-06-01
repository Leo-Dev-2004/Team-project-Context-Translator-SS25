// frontend/src/modules/QueueDisplay.js

// Instead of importing global queue variables from app.js,
// we'll now receive them via a setter function for better modularity.
let _queues = {}; // Private variable to hold queue instances

// Function to set the queue instances
function setQueues(queues) {
    _queues = queues;
    console.log("QueueDisplay: Queues initialized.");
}

const MAX_VISIBLE_ITEMS = 20; // This variable seems unused in the updateQueueDisplay function
let lastUpdateTime = 0;
const UPDATE_THROTTLE_MS = 100;

function updateQueueDisplay(queue, elementId) {
    if (typeof elementId !== 'string' || !elementId) {
        console.error('updateQueueDisplay: elementId parameter is required and must be a string. Received:', elementId);
        return;
    }

    const displayElement = document.getElementById(elementId);
    if (!displayElement) {
        console.error(`Display element with ID "${elementId}" not found in the DOM.`);
        return;
    }

    // Changed from queue.peekAll to queue.getCurrentItemsForDisplay
    if (!queue || typeof queue.getCurrentItemsForDisplay !== 'function') {
        console.error(`Queue for element "${elementId}" is invalid or missing getCurrentItemsForDisplay method. Queue:`, queue);
        return;
    }

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 10;
    // Get a copy of the current items from the queue
    const items = queue.getCurrentItemsForDisplay();
    const itemsToDisplay = items.slice(-MAX_DISPLAY_ITEMS_PER_QUEUE); // Show last N items

    let itemsContainer = displayElement.querySelector('.queue-items');
    let headerContainer = displayElement.querySelector('.queue-header');

    // Recreate header and items container if they don't exist
    if (!headerContainer || !itemsContainer) {
        displayElement.innerHTML = ''; // Clear everything if structure is not as expected

        headerContainer = document.createElement('div');
        headerContainer.className = 'queue-header';
        headerContainer.innerHTML = `
            <span>Type</span>
            <span>ID</span>
            <span>Status</span>
            <span>Timestamp</span>
        `;
        displayElement.appendChild(headerContainer);

        itemsContainer = document.createElement('div');
        itemsContainer.className = 'queue-items';
        displayElement.appendChild(itemsContainer);
    } else {
        // Only clear items container if header exists, keeping header.
        itemsContainer.innerHTML = '';
    }

    if (items.length > MAX_DISPLAY_ITEMS_PER_QUEUE) {
        const overflowDiv = document.createElement('div');
        overflowDiv.className = 'log-overflow';
        overflowDiv.textContent = `Showing last ${itemsToDisplay.length} of ${items.length} messages.`;
        itemsContainer.appendChild(overflowDiv);
    }

    itemsToDisplay.forEach(message => {
        const data = message.data || {};
        let id = message.id || data.id || data.original_id || 'N/A';
        let type = message.type || 'unknown';
        let status = data.status || 'N/A';
            
        // Special handling for command messages
        if (type === 'command') {
            type = `command: ${data.command || 'N/A'}`;
            id = data.client_id || 'N/A';
            status = 'pending';
        }

        const timestamp = message.timestamp ? new Date(message.timestamp * 1000).toLocaleTimeString() : 'N/A';
        const itemElement = document.createElement('div');
        itemElement.className = 'queue-item';
        itemElement.innerHTML = `
            <span>${type}</span>
            <span>${String(id).substring(0, 8)}...</span>
            <span class="${getStatusClass(status)}">${status}</span>
            <span>${timestamp}</span>
        `;
        itemsContainer.appendChild(itemElement);
    });
}

function getStatusClass(status) {
    if (!status) return '';
    
    const statusLower = status.toLowerCase();
    if (statusLower.startsWith('error_')) {
        return 'status-error';
    }
    
    switch (statusLower) {
        case 'pending': return 'status-pending';
        case 'pending_frontend': return 'status-pending-frontend';
        case 'urgent': return 'status-urgent';
        case 'processing': return 'status-processing';
        case 'processed': return 'status-processed';
        case 'generated': return 'status-generated';
        default: return '';
    }
}

function updateQueueCounters() {
    // Ensure _queues are initialized before accessing
    if (!_queues.frontendDisplayQueue || !_queues.frontendActionQueue || !_queues.toBackendQueue || !_queues.fromBackendQueue) {
        // console.warn("QueueDisplay: Queues not fully initialized for counter update.");
        return;
    }

    const toFrontendCountElem = document.getElementById('toFrontendCount');
    const fromFrontendCountElem = document.getElementById('fromFrontendCount');
    const toBackendCountElem = document.getElementById('toBackendCount');
    const fromBackendCountElem = document.getElementById('fromBackendCount');

    if (toFrontendCountElem) toFrontendCountElem.textContent = _queues.frontendDisplayQueue.size();
    if (fromFrontendCountElem) fromFrontendCountElem.textContent = _queues.frontendActionQueue.size();
    if (toBackendCountElem) toBackendCountElem.textContent = _queues.toBackendQueue.size();
    if (fromBackendCountElem) fromBackendCountElem.textContent = _queues.fromBackendQueue.size();
}

function updateAllQueueDisplays() {
    // Only update if _queues are available
    if (Object.keys(_queues).length === 0) {
        // console.warn("QueueDisplay: Cannot update displays, queues not set yet.");
        return;
    }

    const now = performance.now();
    if (now - lastUpdateTime < UPDATE_THROTTLE_MS) {
        requestAnimationFrame(updateAllQueueDisplays);
        return;
    }
    lastUpdateTime = now;

    // IMPORTANT: Make sure the arguments are (QUEUE_OBJECT, 'ELEMENT_ID_STRING')
    updateQueueDisplay(_queues.frontendActionQueue, 'fromFrontendQueueDisplay');
    updateQueueDisplay(_queues.toBackendQueue, 'toBackendQueueDisplay');
    updateQueueDisplay(_queues.fromBackendQueue, 'fromBackendQueueDisplay');
    updateQueueDisplay(_queues.frontendDisplayQueue, 'toFrontendQueueDisplay');

    updateQueueCounters();
}

// Global log functions (kept separate for direct access from anywhere)
export function updateSystemLog(message) {
    const logElement = document.getElementById('systemLog'); // Corrected ID to 'systemLog'
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        const msgText = typeof message === 'object' && message !== null ?
                        (message.message || JSON.stringify(message)) :
                        String(message);
        const entry = document.createElement('p'); // Changed to p for consistency with other new logs
        entry.textContent = `[${timestamp}] ${msgText}`;
        logElement.prepend(entry); // Add to the top
        // Keep log size manageable
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

export function updateSimulationLog(data) {
    const logElement = document.getElementById('simulation_log');
    if (logElement) {
        const messageText = `Sim Update: ID=${data.id || 'N/A'}, Status=${data.status || 'N/A'}`;
        const entry = document.createElement('p'); // Changed to p
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${messageText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

export function updateStatusLog(message) {
    const logElement = document.getElementById('statusLog'); // Corrected ID to 'statusLog'
    if (logElement) {
        const msgText = typeof message === 'object' && message !== null ?
                        (message.message || JSON.stringify(message)) :
                        String(message);
        const entry = document.createElement('p'); // Changed to p
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${msgText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

// Add to existing CSS classes
const styleElement = document.createElement('style');
styleElement.textContent = `
    .status-error {
        color: #ff0000;
        font-weight: bold;
    }
    #reconnectStatus {
        position: fixed;
        bottom: 10px;
        right: 10px;
        background: #ffcc00;
        padding: 5px 10px;
        border-radius: 5px;
        display: none;
    }
`;
document.head.appendChild(styleElement);

export function updateDataLog(data) {
    const logElement = document.getElementById('dataLog');
    if (logElement) {
        const entry = document.createElement('div');
        entry.className = 'data-entry';
        
        if (data.text) {
            entry.textContent = data.text;
        } else {
            entry.textContent = JSON.stringify(data, null, 2);
        }
        
        logElement.prepend(entry);
        if (logElement.children.length > 50) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

export function updateTestLog(message) {
    const logElement = document.getElementById('testLog'); // Corrected ID to 'testLog'
    if (logElement) {
        const msgText = typeof message === 'object' && message !== null ?
                        (message.message || JSON.stringify(message)) :
                        String(message);
        const entry = document.createElement('p'); // Changed to p
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${msgText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

// Export the setQueues function along with others
export {
    updateAllQueueDisplays,
    updateQueueDisplay, // Though not directly used externally after this change
    updateQueueCounters, // Not directly used externally after this change
    setQueues
};
