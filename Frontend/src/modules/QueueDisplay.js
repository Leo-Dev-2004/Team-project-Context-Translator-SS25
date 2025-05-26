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

function updateQueueDisplay(queueName, queue, elementId) {
    if (!elementId) {
        console.error('updateQueueDisplay: elementId parameter is required');
        return;
    }
    
    const displayElement = document.getElementById(elementId);
    if (!displayElement) {
        console.error(`Display element with ID "${elementId}" not found`);
        return;
    }

    if (!queue) {
        console.error(`Queue "${queueName}" is undefined`);
        return;
    }

    if (typeof queue.peekAll !== 'function') {
        console.error(`Queue "${queueName}" does not have peekAll method`);
        return;
    }

    const items = queue.peekAll().slice(-10); // Show last 10 items
    if (!Array.isArray(items)) {
        console.error(`Queue "${queueName}" did not return valid items array`);
        return;
    }
    displayElement.innerHTML = items.map(item => 
        `<div class="queue-item">
            <strong>${item.type}</strong>: ${JSON.stringify(item.data)}
        </div>`
    ).join('');
}

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
        updateQueueLog('toFrontendQueueDisplay', toFrontendQueue);
        updateQueueLog('fromFrontendQueueDisplay', fromFrontendQueue);
        updateQueueLog('toBackendQueueDisplay', toBackendQueue);
        updateQueueLog('fromBackendQueueDisplay', fromBackendQueue);
        updateQueueCounters();
    });
}

// Frontend/src/modules/QueueDisplay.js (only the updateQueueLog function)

function updateQueueLog(elementId, queueOrMessage) {
    const logElement = document.getElementById(elementId);
    if (!logElement) {
        console.error(`Error: Log element with ID '${elementId}' not found.`);
        return;
    }
    
    // Sicherstellen, dass das Element sichtbar ist
    if (logElement.style.display === 'none') {
        logElement.style.display = 'block';
    }

    // Wenn zweiter Parameter eine Queue ist
    if (queueOrMessage && typeof queueOrMessage.peekAll === 'function') {
        const queue = queueOrMessage;

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 10;
    const itemsToDisplay = queue.peekAll().slice(-MAX_DISPLAY_ITEMS_PER_QUEUE);

    let htmlContent = '';
    if (queue.size() > MAX_DISPLAY_ITEMS_PER_QUEUE) {
        htmlContent += `<div class="log-overflow">Showing last ${itemsToDisplay.length} of ${queue.size()} messages.</div>`;
    }

    const itemsContainer = document.querySelector(`#${elementId} .queue-items`);
    if (itemsContainer) {
        itemsContainer.innerHTML = '';
        
        itemsToDisplay.forEach(message => {
            const data = message.data || {};
            const id = data.id || data.original_id || 'N/A';
            const type = message.type || 'unknown';
            const status = data.status || 'N/A';
            
            const itemElement = document.createElement('div');
            itemElement.className = 'queue-item';
            itemElement.innerHTML = `
                <span>${type}</span>
                <span>${String(id).substring(0, 8)}...</span>
                <span class="${getStatusClass(status)}">${status}</span>
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
            default: return '';
        }
    }
    } 
    // Wenn zweiter Parameter eine direkte Nachricht ist
    else if (typeof queueOrMessage === 'string') {
        logElement.textContent += queueOrMessage + '\n';
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
