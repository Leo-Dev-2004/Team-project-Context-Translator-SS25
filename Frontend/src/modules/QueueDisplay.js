// QueueDisplay.js
import {
    toFrontendQueue,
    fromFrontendQueue, 
    toBackendQueue,
    fromBackendQueue
} from './MessageQueue.js';

const MAX_VISIBLE_ITEMS = 20;
let lastUpdateTime = 0;
const UPDATE_THROTTLE_MS = 100;

// lastMessage is currently a global variable, needs to be passed or managed differently
// For now, we'll keep it global in app.js and pass it, or you can consider encapsulating it.
// Let's assume it's passed as an argument to updateQueueCounters or QueueDisplay.init()


function updateAllQueueDisplays() {
    console.log("DEBUG: updateAllQueueDisplays called.");
    const now = performance.now();
    if (now - lastUpdateTime < UPDATE_THROTTLE_MS) {
        requestAnimationFrame(updateAllQueueDisplays);
        return;
        }
    
        // Close the updateQueueLog function
    
    lastUpdateTime = now;

    Promise.resolve().then(() => {
        updateQueueDisplay(toFrontendQueue, 'toFrontendQueueDisplay');
        updateQueueDisplay(fromFrontendQueue, 'fromFrontendQueueDisplay');
        updateQueueDisplay(toBackendQueue, 'toBackendQueueDisplay');
        updateQueueDisplay(fromBackendQueue, 'fromBackendQueueDisplay');
        updateQueueCounters();
    });
}

// Frontend/src/modules/QueueDisplay.js (only the updateQueueLog function)

function updateQueueDisplay(queue, elementId) {
    if (!elementId) {
        console.error('updateQueueDisplay: elementId parameter is required');
        return;
    }

    const displayElement = document.getElementById(elementId);
    if (!displayElement) {
        console.error(`Display element with ID "${elementId}" not found`);
        return;
    }

    if (!queue || typeof queue.peekAll !== 'function') {
        console.error(`Queue for element "${elementId}" is invalid or missing peekAll method`);
        return;
    }

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 10;
    const itemsToDisplay = queue.peekAll().slice(-MAX_DISPLAY_ITEMS_PER_QUEUE);

    // Find or create the .queue-items container
    let itemsContainer = displayElement.querySelector('.queue-items');
    if (!itemsContainer) {
        // If the container doesn't exist, create it and prepend a header if needed
        const header = document.createElement('div');
        header.className = 'queue-header';
        header.innerHTML = `
            <span>Type</span>
            <span>ID</span>
            <span>Status</span>
            <span>Timestamp</span>
        `;
        displayElement.appendChild(header); // Append header
        
        itemsContainer = document.createElement('div');
        itemsContainer.className = 'queue-items';
        displayElement.appendChild(itemsContainer); // Append items container
    } else {
        // Clear existing content if container already exists
        itemsContainer.innerHTML = '';
    }

    // Add overflow message if needed
    if (queue.size() > MAX_DISPLAY_ITEMS_PER_QUEUE) {
        const overflowDiv = document.createElement('div');
        overflowDiv.className = 'log-overflow';
        overflowDiv.textContent = `Showing last ${itemsToDisplay.length} of ${queue.size()} messages.`;
        itemsContainer.appendChild(overflowDiv);
    }

    itemsToDisplay.forEach(message => {
        const data = message.data || {};
        const id = data.id || data.original_id || 'N/A';
        const type = message.type || 'unknown';
        const status = data.status || 'N/A';

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
    switch (status.toLowerCase()) {
        case 'pending': return 'status-pending';
        case 'urgent': return 'status-urgent';
        case 'processing': return 'status-processing';
        case 'processed': return 'status-processed';
        case 'generated': return 'status-generated';
        case 'pending_frontend': return 'status-pending_frontend';
        default: return '';
    }
}


function updateQueueCounters() {
    document.getElementById('toFrontendCount').textContent = toFrontendQueue.size();
    document.getElementById('fromFrontendCount').textContent = fromFrontendQueue.size();
    document.getElementById('toBackendCount').textContent = toBackendQueue.size();
    document.getElementById('fromBackendCount').textContent = fromBackendQueue.size();

    if (console.debug) {
        console.debug('Queue Stats:', {
            toFrontend: toFrontendQueue.size(),
            fromFrontend: fromFrontendQueue.size(),
            toBackend: toBackendQueue.size(),
            fromBackend: fromBackendQueue.size()
        });
    }
}
    
    
// Export the functions that need to be called externally
export { updateAllQueueDisplays, updateQueueLog, updateQueueCounters, updateQueueDisplay };
