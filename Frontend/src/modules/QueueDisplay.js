// frontend/src/modules/QueueDisplay.js

// Consolidated mapping of logical queue names (from MessageQueue.js, WebSocketManager.js, or backend payloads)
// to their corresponding HTML element IDs for display.
const queueDisplayMappings = {
    // Frontend's internal queues (names used when MessageQueue.js instances are created and subscribe):
    // These keys match the `queueName` property of your MessageQueue instances (e.g., new MessageQueue('toBackendQueue'))
    'toBackendQueue': 'frontendOutgoingQueueDisplay',    // Maps to the HTML div for "Frontend Outgoing"
    'fromBackendQueue': 'frontendIncomingQueueDisplay',  // Maps to the HTML div for "Frontend Incoming"

    // Backend's queue status updates (names found in the payload from backend 'system.queue_status_update'):
    // These keys should match the exact names used by your backend when reporting queue sizes.
    // Based on previous discussions, your backend should be sending 'from_frontend_queue', 'to_frontend_queue', etc.
    'from_frontend_queue': 'backendIncomingQueueDisplay', // Backend's queue receiving messages *from* frontend
    'to_frontend_queue': 'backendOutgoingQueueDisplay',   // Backend's queue sending messages *to* frontend
    'dead_letter_queue': 'deadLetterQueueDisplay',        // Backend's Dead Letter Queue

    // Remove the old/redundant mappings if your backend and WebSocketManager are now consistent.
    // If your backend *still* sends 'incoming' or 'outgoing' as queue names in the payload,
    // you would map them here accordingly, e.g.:
    // 'incoming': 'backendIncomingQueueDisplay',
    // 'outgoing': 'backendOutgoingQueueDisplay',
    // But ideally, the backend uses the clearer 'from_frontend_queue' and 'to_frontend_queue'.
    // The "Special names used by WebSocketManager.js" section is also no longer needed as
    // WebSocketManager subscribes directly to the `MessageQueue` instances (`toBackendQueue`, `fromBackendQueue`).
};


/**
 * Updates a specific queue's display in the HTML.
 * This function is designed to be called by MessageQueue subscriptions
 * or by WebSocketManager when receiving backend queue status updates.
 *
 * @param {string} queueName - The logical name of the queue (e.g., 'toBackendQueue' for frontend, 'incoming' for backend status).
 * @param {number} size - The current size of the queue.
 * @param {Array<Object>} items - An array of message objects currently in the queue.
 */
function updateQueueDisplay(queueName, size, items) {
    const elementId = queueDisplayMappings[queueName];

    // --- START DEBUG LOGGING ---
    console.log(`[QueueDisplay] Attempting to update for queueName: "${queueName}"`);
    console.log(`[QueueDisplay]   Mapped to HTML ID: "${elementId}"`);
    console.log(`[QueueDisplay]   Received Size: ${size}`);
    console.log(`[QueueDisplay]   Received Items Count: ${items ? items.length : 'N/A'}`);
    // --- END DEBUG LOGGING ---

    if (!elementId) {
        console.warn(`updateQueueDisplay: No HTML element mapping found for logical queue name "${queueName}".`);
        return;
    }

    const displayElement = document.getElementById(elementId);
    if (!displayElement) {
        console.error(`Display element with ID "${elementId}" not found in the DOM for queue "${queueName}".`);
        return;
    }

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 5; // Reverted to 5 for consistency with previous example, can be adjusted

    // Update the queue size text (e.g., "(Size: X)")
    const sizeElement = displayElement.querySelector('.queue-size');
    if (sizeElement) {
        sizeElement.textContent = `(Size: ${size})`;
    } else {
        // This means the span with class="queue-size" is missing inside your queue container.
        console.warn(`QueueDisplay.js: '.queue-size' span not found inside #${elementId}.`);
    }

    // Get the container for the list of messages
    const itemsContainer = displayElement.querySelector('.message-items-container');
    if (!itemsContainer) {
        console.error(`Queue items container (.message-items-container) not found inside #${elementId}.`);
        return;
    }

    itemsContainer.innerHTML = ''; // Clear existing items

    // Handle empty or null items array
    if (!items || items.length === 0) {
        const noItemsDiv = document.createElement('div');
        noItemsDiv.className = 'queue-item-placeholder text-center text-gray-500 py-4 text-sm';
        noItemsDiv.textContent = 'No messages'; // Changed from 'Queue is empty.' for brevity in small cards
        itemsContainer.appendChild(noItemsDiv);
        return; // Exit if no items
    }

    // --- Dead Letter Queue Specific Handling ---
    if (elementId === 'deadLetterQueueDisplay') {
        const ul = document.createElement('ul');
        ul.className = 'list-disc list-inside text-sm text-red-700 space-y-1'; // Added red color for DLQ
        items.slice(0, MAX_DISPLAY_ITEMS_PER_QUEUE).forEach(item => { // Limit DLQ items too
            const li = document.createElement('li');
            li.textContent = `${item.type || 'N/A'} (ID: ${item.id ? String(item.id).substring(0, 8) : 'N/A'}) - ${new Date(item.timestamp * 1000).toLocaleTimeString()}`; // Assuming backend timestamp in seconds
            ul.appendChild(li);
        });
        itemsContainer.appendChild(ul);

        if (items.length > MAX_DISPLAY_ITEMS_PER_QUEUE) {
            const overflowDiv = document.createElement('div');
            overflowDiv.className = 'log-overflow text-center text-gray-500 py-2 text-sm';
            overflowDiv.textContent = `Showing last ${MAX_DISPLAY_ITEMS_PER_QUEUE} of ${items.length} DLQ messages.`;
            itemsContainer.appendChild(overflowDiv);
        }
        return; // Exit as dead letter queue is handled
    }

    // --- Standard Queue Display Logic (for non-Dead Letter Queues) ---
    const itemsToDisplay = items.slice(-MAX_DISPLAY_ITEMS_PER_QUEUE); // Show last N items


    // Add overflow message if too many items
    if (items.length > MAX_DISPLAY_ITEMS_PER_QUEUE) {
        const overflowDiv = document.createElement('div');
        overflowDiv.className = 'log-overflow text-center text-gray-500 py-2 text-sm';
        overflowDiv.textContent = `Showing last ${itemsToDisplay.length} of ${items.length} messages.`;
        itemsContainer.appendChild(overflowDiv);
    }

    itemsToDisplay.forEach(message => {
        // Ensure message and its properties exist to prevent errors
        const data = message.payload || {}; // Use payload for structured message data
        let id = (message.id || data.id || data.original_id || 'N/A').toString();
        let type = message.type || 'unknown';
        let status = data.status || 'N/A'; // Assuming status might be in payload

        if (type === 'command' && data.command) { // Check if data.command exists for command type
            type = `command: ${data.command}`;
            // id = (data.client_id || id).toString(); // Keep original message ID for tracking
            // status = 'pending'; // Command might have its own status
        }
        // Handle system.queue_status_update messages gracefully
        if (type === 'system.queue_status_update') {
             type = 'Queue Status';
             id = 'Monitor';
             status = 'updated';
             // You might want to display more details about the status update if needed
        }


        // Timestamps from backend are likely in seconds (Python's time.time()), JS Date needs milliseconds
        const timestampMs = message.timestamp < 1e12 ? message.timestamp * 1000 : message.timestamp;
        const timestamp = new Date(timestampMs).toLocaleTimeString();

        const itemElement = document.createElement('div');
        itemElement.classList.add('queue-item', 'p-2', 'mb-1', 'rounded', 'flex', 'justify-between', 'items-center', 'text-xs', 'bg-gray-200');
        itemElement.dataset.id = id; // Useful for debugging or later interactions

        // Construct inner HTML for standard queue item
        itemElement.innerHTML = `
            <span class="font-semibold">${type}</span>
            <span class="text-gray-600">ID: ${id.substring(0, Math.min(id.length, 8))}...</span>
            <span class="${getStatusClass(status)}">${status}</span>
            <span class="text-gray-500">${timestamp}</span>
        `;
        itemsContainer.appendChild(itemElement);
    });
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
        case 'updated': return 'text-yellow-600 font-medium'; // For queue_status_update messages
        default: return 'text-gray-700';
    }
}

// --- Global Log Functions (exported for direct use from app.js or WebSocketManager) ---
// These remain largely the same, ensure they map to correct HTML IDs if you change them.

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
    .status-updated { /* For queue_status_update messages */
        color: #f59e0b; /* Yellow-600 */
        font-weight: medium;
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
    updateTranscriptionLog,
};