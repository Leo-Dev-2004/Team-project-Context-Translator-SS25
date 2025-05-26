// frontend/src/modules/QueueDisplay.js
import {
    frontendDisplayQueue,
    frontendActionQueue,
    toBackendQueue,
    fromBackendQueue
} from '../app.js';

const MAX_VISIBLE_ITEMS = 20;
let lastUpdateTime = 0;
const UPDATE_THROTTLE_MS = 100;

function updateQueueDisplay(queue, elementId) {
    // This is LINE 16, where the error is detected if arguments are swapped upstream
    if (typeof elementId !== 'string' || !elementId) {
        console.error('updateQueueDisplay: elementId parameter is required and must be a string. Received:', elementId);
        return;
    }

    const displayElement = document.getElementById(elementId);
    if (!displayElement) {
        console.error(`Display element with ID "${elementId}" not found in the DOM.`);
        return;
    }

    if (!queue || typeof queue.peekAll !== 'function') {
        console.error(`Queue for element "${elementId}" is invalid or missing peekAll method. Queue:`, queue);
        return;
    }

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 10;
    const itemsToDisplay = queue.peekAll().slice(-MAX_DISPLAY_ITEMS_PER_QUEUE);

    let itemsContainer = displayElement.querySelector('.queue-items');
    let headerContainer = displayElement.querySelector('.queue-header');

    if (!headerContainer || !itemsContainer) {
        displayElement.innerHTML = '';

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
        itemsContainer.innerHTML = '';
    }

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
        case 'pending_frontend': return 'status-pending-frontend';
        case 'urgent': return 'status-urgent';
        case 'processing': return 'status-processing';
        case 'processed': return 'status-processed';
        case 'generated': return 'status-generated';
        default: return '';
    }
}

function updateQueueCounters() {
    const toFrontendCountElem = document.getElementById('toFrontendCount');
    const fromFrontendCountElem = document.getElementById('fromFrontendCount');
    const toBackendCountElem = document.getElementById('toBackendCount');
    const fromBackendCountElem = document.getElementById('fromBackendCount');

    if (toFrontendCountElem) toFrontendCountElem.textContent = frontendDisplayQueue.size();
    if (fromFrontendCountElem) fromFrontendCountElem.textContent = frontendActionQueue.size();
    if (toBackendCountElem) toBackendCountElem.textContent = toBackendQueue.size();
    if (fromBackendCountElem) fromBackendCountElem.textContent = fromBackendQueue.size();
}

// THIS IS THE CRITICAL FUNCTION TO CHECK FOR SWAPPED ARGUMENTS
function updateAllQueueDisplays() {
    const now = performance.now();
    if (now - lastUpdateTime < UPDATE_THROTTLE_MS) {
        requestAnimationFrame(updateAllQueueDisplays);
        return;
    }
    lastUpdateTime = now;

    // IMPORTANT: Make sure the arguments are (QUEUE_OBJECT, 'ELEMENT_ID_STRING')
    updateQueueDisplay(frontendActionQueue, 'fromFrontendQueueDisplay'); // Correct order
    updateQueueDisplay(toBackendQueue, 'toBackendQueueDisplay');         // Correct order
    updateQueueDisplay(fromBackendQueue, 'fromBackendQueueDisplay');     // Correct order
    updateQueueDisplay(frontendDisplayQueue, 'toFrontendQueueDisplay');  // Correct order

    updateQueueCounters();
}

function updateSystemLog(data) {
    const logElement = document.getElementById('system_log');
    if (logElement) {
        const messageText = typeof data === 'string' ? data : (data.message || JSON.stringify(data));
        logElement.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${messageText}</div>`;
        logElement.scrollTop = logElement.scrollHeight;
    }
}

function updateSimulationLog(data) {
    const logElement = document.getElementById('simulation_log');
    if (logElement) {
        const messageText = `Sim Update: ID=${data.id || 'N/A'}, Status=${data.status || 'N/A'}`;
        logElement.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${messageText}</div>`;
        logElement.scrollTop = logElement.scrollHeight;
    }
}

function updateStatusLog(message) {
    const logElement = document.getElementById('status_log');
    if (logElement) {
        logElement.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${message}</div>`;
        logElement.scrollTop = logElement.scrollHeight;
    }
}

function updateTestLog(message) {
    const logElement = document.getElementById('test_log');
    if (logElement) {
        logElement.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${message}</div>`;
        logElement.scrollTop = logElement.scrollHeight;
    }
}

export {
    updateAllQueueDisplays,
    updateQueueDisplay,
    updateQueueCounters,
    updateSystemLog,
    updateSimulationLog,
    updateStatusLog,
    updateTestLog
};
