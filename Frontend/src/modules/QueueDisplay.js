// frontend/src/modules/QueueDisplay.js

// Map backend queue names to frontend display IDs for easier lookup
const backendQueueDisplayMap = {
    // These are the *backend's* internal queue names as sent in `queue_status_update` messages
    'from_frontend': 'backendIncomingQueueDisplay', // Backend's queue for messages *from* frontend
    'to_backend': 'backendProcessingQueueDisplay', // Added this to match the flow description if you have a 'to_backend' queue
    'from_backend': 'backendServiceQueueDisplay', // Added this for internal backend service responses
    'to_frontend': 'backendOutgoingQueueDisplay',  // Backend's queue for messages *to* frontend
    'dead_letter': 'deadLetterQueueDisplay',
};

// Map frontend's *local* queue names to their display IDs
const frontendQueueDisplayMap = {
    'toBackendQueue': 'frontendOutgoingQueueDisplay', // Frontend's queue for messages *to* backend
    'fromBackendQueue': 'frontendIncomingQueueDisplay', // Frontend's queue for messages *from* backend
    'frontendActionQueue': 'frontendActionQueueDisplay', // Your existing frontend queue if you use it
    'frontendDisplayQueue': 'frontendDisplayQueueDisplay', // Your existing frontend queue if you use it
};

/**
 * Updates a specific queue's display in the HTML.
 * This function is designed to be called by MessageQueue subscriptions
 * or by WebSocketManager when receiving backend queue status updates.
 *
 * @param {string} queueName - The logical name of the queue (e.g., 'toBackendQueue' for frontend, 'from_frontend' for backend).
 * @param {number} size - The current size of the queue.
 * @param {Array<Object>} items - An array of message objects currently in the queue.
 */
function updateQueueDisplay(queueName, size, items) {
    let elementId;

    // Check if it's a backend queue name or a frontend local queue name
    if (backendQueueDisplayMap[queueName]) {
        elementId = backendQueueDisplayMap[queueName];
    } else if (frontendQueueDisplayMap[queueName]) {
        elementId = frontendQueueDisplayMap[queueName];
    } else {
        console.warn(`updateQueueDisplay: No mapping found for queueName "${queueName}".`);
        return;
    }

    const displayElement = document.getElementById(elementId);
    if (!displayElement) {
        console.error(`Display element with ID "${elementId}" not found in the DOM for queue "${queueName}".`);
        return;
    }

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 10; // Max items to show in the detailed log view

    // Update the queue counter
    const queueCountSpan = document.getElementById(elementId.replace('Display', 'Count'));
    if (queueCountSpan) {
        queueCountSpan.textContent = size;
    }

    // Special handling for Dead Letter Queue, as its structure might differ
    if (elementId === 'deadLetterQueueDisplay') {
        const itemsContainer = displayElement.querySelector('.queue-items');
        if (itemsContainer) {
            itemsContainer.innerHTML = ''; // Clear existing items

            if (items && items.length > 0) {
                const ul = document.createElement('ul');
                ul.className = 'list-disc list-inside mt-2 text-sm dead-letter-list';
                items.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = `${item.type || 'N/A'} (ID: ${item.id ? String(item.id).substring(0, 8) : 'N/A'}) - ${new Date(item.timestamp * 1000).toLocaleTimeString()}`; // Assuming backend timestamp is in seconds
                    ul.appendChild(li);
                });
                itemsContainer.appendChild(ul);
            } else {
                const noItemsDiv = document.createElement('div');
                noItemsDiv.className = 'queue-item-placeholder text-center text-gray-500 py-4';
                noItemsDiv.textContent = 'Queue is empty.';
                itemsContainer.appendChild(noItemsDiv);
            }
        }
        return; // Exit as dead letter queue is handled
    }

    // --- Standard Queue Display Logic (for non-Dead Letter Queues) ---
    const itemsToDisplay = items.slice(-MAX_DISPLAY_ITEMS_PER_QUEUE); // Show last N items

    const itemsContainer = displayElement.querySelector('.queue-items');
    if (!itemsContainer) {
        console.error(`Queue items container (.queue-items) not found inside #${elementId}.`);
        return;
    }

    itemsContainer.innerHTML = ''; // Clear existing items for standard queues

    // Add overflow message if too many items
    if (items.length > MAX_DISPLAY_ITEMS_PER_QUEUE) {
        const overflowDiv = document.createElement('div');
        overflowDiv.className = 'log-overflow text-center text-gray-500 py-2 text-sm';
        overflowDiv.textContent = `Showing last ${itemsToDisplay.length} of ${items.length} messages.`;
        itemsContainer.appendChild(overflowDiv);
    }

    if (itemsToDisplay.length === 0) {
        const noItemsDiv = document.createElement('div');
        noItemsDiv.className = 'queue-item-placeholder text-center text-gray-500 py-4';
        noItemsDiv.textContent = 'Queue is empty.';
        itemsContainer.appendChild(noItemsDiv);
    } else {
        itemsToDisplay.forEach(message => {
            const data = message.data || {};
            let id = (message.id || data.id || data.original_id || 'N/A').toString();
            let type = message.type || 'unknown';
            let status = data.status || 'N/A';

            if (type === 'command') {
                type = `command: ${data.command || 'N/A'}`;
                id = (data.client_id || id).toString();
                status = 'pending';
            }

            // Timestamps from backend are likely in seconds (Python's time.time()), JS Date needs milliseconds
            const timestampMs = message.timestamp < 1e12 ? message.timestamp * 1000 : message.timestamp;
            const timestamp = new Date(timestampMs).toLocaleTimeString();

            const itemElement = document.createElement('div');
            itemElement.classList.add('queue-item', 'p-2', 'mb-1', 'rounded', 'flex', 'justify-between', 'items-center', 'text-xs', 'bg-gray-200');
            itemElement.dataset.id = id;

            itemElement.innerHTML = `
                <span class="font-semibold">${type}</span>
                <span class="text-gray-600">ID: ${id.substring(0, 8)}...</span>
                <span class="${getStatusClass(status)}">${status}</span>
                <span class="text-gray-500">${timestamp}</span>
            `;
            itemsContainer.appendChild(itemElement);
        });
    }
}

/**
 * Determines the CSS class for a message status for visual styling.
 * @param {string} status - The status string (e.g., 'pending', 'processed', 'error_parse').
 * @returns {string} The corresponding CSS class.
 */
function getStatusClass(status) {
    if (!status) return '';

    const statusLower = status.toLowerCase();
    if (statusLower.startsWith('error')) {
        return 'text-red-600 font-bold';
    }

    switch (statusLower) {
        case 'pending': return 'text-gray-500';
        case 'processing': return 'text-blue-600';
        case 'processed':
        case 'success':
        case 'completed': return 'text-green-600 font-medium';
        case 'urgent': return 'text-orange-600 font-bold';
        case 'generated': return 'text-purple-600';
        default: return 'text-gray-700';
    }
}

// --- Global Log Functions (exported for direct use from app.js or WebSocketManager) ---

function updateSystemLog(message) {
    const logElement = document.getElementById('system_log');
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        const msgText = typeof message === 'object' && message !== null ?
                        (message.message || JSON.stringify(message)) :
                        String(message);
        const entry = document.createElement('div');
        entry.textContent = `[${timestamp}] ${msgText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

function updateSimulationLog(data) {
    const logElement = document.getElementById('simulation_log');
    if (logElement) {
        const messageText = `Sim Update: ID=${data.id || 'N/A'}, Status=${data.status || 'N/A'}`;
        const entry = document.createElement('div');
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${messageText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

function updateStatusLog(message) {
    const logElement = document.getElementById('status_log');
    if (logElement) {
        const msgText = typeof message === 'object' && message !== null ?
                        (message.message || JSON.stringify(message)) :
                        String(message);
        const entry = document.createElement('div');
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${msgText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

function updateTranscriptionLog(text) {
    const logElement = document.getElementById('transcription_display');
    if (logElement) {
        const entry = document.createElement('div');
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
        logElement.prepend(entry);
        if (logElement.children.length > 50) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

function updateTestLog(message) {
    const logElement = document.getElementById('test_log');
    if (logElement) {
        const msgText = typeof message === 'object' && message !== null ?
                        (message.message || JSON.stringify(message)) :
                        String(message);
        const entry = document.createElement('div');
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${msgText}`;
        logElement.prepend(entry);
        if (logElement.children.length > 100) {
            logElement.removeChild(logElement.lastChild);
        }
    }
}

// Add basic styles directly if not in CSS file
const styleElement = document.createElement('style');
styleElement.textContent = `
    .queue-item {
        transition: background-color 0.3s ease, opacity 0.3s ease, transform 0.3s ease;
    }
    .queue-item:hover {
        background-color: #e0e7ff; /* Lighter blue on hover */
    }
    .status-error {
        color: #dc2626; /* Red-600 */
        font-weight: bold;
    }
    .status-pending {
        color: #6b7280; /* Gray-500 */
    }
    .status-processing {
        color: #3b82f6; /* Blue-500 */
    }
    .status-processed {
        color: #22c55e; /* Green-500 */
        font-weight: medium;
    }
    .status-urgent {
        color: #f97316; /* Orange-500 */
        font-weight: bold;
    }
    .status-generated {
        color: #a855f7; /* Purple-500 */
    }
    #reconnectStatus {
        position: fixed;
        bottom: 10px;
        right: 10px;
        background: #fbbf24; /* Amber-400 */
        color: #333;
        padding: 8px 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        display: none; /* Hidden by default */
        z-index: 1000;
        font-size: 0.9rem;
    }
    .log-overflow {
        font-style: italic;
        color: #777;
        margin-bottom: 8px;
        border-bottom: 1px dashed #ccc;
        padding-bottom: 4px;
    }
    .queue-item-placeholder {
        font-style: italic;
        color: #9ca3af; /* Gray-400 */
    }
`;
document.head.appendChild(styleElement);


// Export all necessary functions
export {
    updateQueueDisplay,
    updateSystemLog,
    updateSimulationLog,
    updateStatusLog,
    updateTestLog,
    updateTranscriptionLog
};