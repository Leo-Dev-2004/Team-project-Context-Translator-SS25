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

function updateQueueDisplay() {
    console.log("DEBUG: updateAllQueueDisplays called.");
    const now = performance.now();
    if (now - lastUpdateTime < UPDATE_THROTTLE_MS) {
        requestAnimationFrame(updateAllQueueDisplays);
        return;
    }
    lastUpdateTime = now;

    Promise.resolve().then(() => {
        updateQueueLog('toFrontendLog', toFrontendQueue);
        updateQueueLog('fromFrontendLog', fromFrontendQueue);
        updateQueueLog('toBackendLog', toBackendQueue);
        updateQueueLog('fromBackendLog', fromBackendQueue);
        updateQueueCounters();
    });
}

// Frontend/src/modules/QueueDisplay.js (only the updateQueueLog function)
export function updateQueueLog(elementId, queue) {
    // console.log(`DEBUG: updateQueueLog called for ${elementId}. Queue size: ${queue.size()}`);

    const logElement = document.getElementById(elementId); // Correct declaration here
    if (!logElement) {
        console.error(`Error: Log element with ID '${elementId}' not found.`);
        return;
    }

    const MAX_DISPLAY_ITEMS_PER_QUEUE = 10;
    const itemsToDisplay = queue.peekAll().slice(-MAX_DISPLAY_ITEMS_PER_QUEUE);

    let htmlContent = '';
    if (queue.size() > MAX_DISPLAY_ITEMS_PER_QUEUE) {
        htmlContent += `<div class="log-overflow">Showing last ${itemsToDisplay.length} of ${queue.size()} messages.</div>`;
    }

    itemsToDisplay.forEach(message => {
        const data = message.data || {};
        const id = data.id || data.original_id || 'N/A';
        const type = message.type || 'unknown';
        // Convert Unix timestamp (seconds) to JS timestamp (milliseconds)
        const timestamp = new Date(message.timestamp * 1000).toLocaleTimeString();
        const status = data.status || 'N/A';
        const content = data.message || data.text || (typeof data === 'object' ? JSON.stringify(data) : data);

        let statusClass = '';
        switch (status) {
            case 'pending':
                statusClass = 'status-pending';
                break;
            case 'urgent':
                statusClass = 'status-urgent';
                break;
            case 'processing':
                statusClass = 'status-processing';
                break;
            case 'processed':
                statusClass = 'status-processed';
                break;
            default:
                statusClass = '';
                break;
        }

        htmlContent += `
            <div class="log-entry">
                <div class="message-header">
                    <span class="message-id">ID: ${String(id).substring(0, 8)}...</span>
                </div>
                <div class="message-body ${statusClass}">
                    <div class="message-type">Type: ${type}</div>
                    <div class="message-timestamp">${timestamp}</div>
                    <div class="message-content">${content}</div>
                </div>
            </div>

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
export { updateQueueDisplay, updateQueueLog, updateQueueCounters };
