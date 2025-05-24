// QueueDisplay.js
import { toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue } from '../app.js';

const MAX_VISIBLE_ITEMS = 20;
let lastUpdateTime = 0;
const UPDATE_THROTTLE_MS = 100;

// lastMessage is currently a global variable, needs to be passed or managed differently
// For now, we'll keep it global in app.js and pass it, or you can consider encapsulating it.
// Let's assume it's passed as an argument to updateQueueCounters or QueueDisplay.init()

export function updateAllQueueDisplays() {
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

function updateQueueLog(logId, queue) {
    const logElement = document.getElementById(logId);
    if (!logElement) {
        console.warn(`Queue log element not found: ${logId}`);
        return;
    }

    const items = queue.queue.slice(-20); // Get last 20 items
    const now = Date.now();
    
    logElement.innerHTML = items.map(item => {
        const timeDiff = (now - (item.timestamp * 1000)) / 1000;
        return `
        <div class="log-entry">
            <div class="message-header">
                <span class="message-type ${item.type}">${item.type}</span>
                <span class="message-id">${item.id || 'N/A'}</span>
            </div>
            <div class="message-content">
                ${JSON.stringify(item.data, null, 2)}
            </div>
            <div class="message-footer">
                <span>${timeDiff.toFixed(1)}s ago</span>
                <span class="message-status">${item.status || 'pending'}</span>
            </div>
        </div>`;
    }).join('');

    // Auto-scroll to bottom
    logElement.scrollTop = logElement.scrollHeight;
    const logElement = document.getElementById(logId);
    if (!logElement) {
        console.warn(`DEBUG: Log element not found for ID: ${logId}`);
        return;
    }

    const items = [...queue.queue].reverse();
    const now = Date.now();

    let visibleItems = items;
    if (logId === 'toFrontendLog') {
        visibleItems = items.sort((a, b) => {
            if (a.type === 'error') return -1;
            if (b.type === 'error') return 1;
            if (a.type === 'status_update') return -1;
            if (b.type === 'status_update') return 1;
            return 0;
        });
    }

    visibleItems = visibleItems.slice(0, MAX_VISIBLE_ITEMS);

    console.log("Generating HTML for", visibleItems.length, "visible items");
    const htmlContent = visibleItems.map((item, index) => {
        console.log(`Processing item ${index}:`, item.type);
        const timeDiff = (now - (item.timestamp * 1000)) / 1000;
        let statusClass = '';
        let content = '';

        if (item.type === 'status_update') {
            statusClass = `status-${item.data.status || 'unknown'}`;
            content = `<span class="message-id">${item.data.original_id || 'N/A'}</span>:
                       ${item.data.status?.toUpperCase() || 'UNKNOWN'} (${item.data.progress}%)<br>
                       <small>${timeDiff.toFixed(1)}s ago</small>`;
        } else if (item.type === 'error') {
            statusClass = 'status-error';
            content = `<span class="message-id">ERROR</span>:
                       ${item.data.message || 'Unknown error'}<br>
                       ${item.data.details ? `<small>${item.data.details}</small><br>` : ''}
                       <small>${timeDiff.toFixed(1)}s ago</small>`;
        } else if (item.data && item.data.id) {
            const itemStatus = item.status || item.data?.status;
            if (itemStatus === 'created') statusClass = 'status-created';
            else if (itemStatus === 'processing') statusClass = 'status-processing';
            else if (itemStatus === 'processed') statusClass = 'status-processed';
            content = `<span class="message-id">${item.data.id}</span>: ${item.data.data || JSON.stringify(item.data)}<br>
                      <small>${(itemStatus?.toUpperCase() || '')} ${timeDiff.toFixed(1)}s ago</small>`;
        } else { // Generic message display (test_message, simulation_update if not special cased by id)
            content = `<span class="message-type">${item.type || 'message'}</span>:
                       ${JSON.stringify(item.data || item)}<br>
                       <small>${timeDiff.toFixed(1)}s ago</small>`;
        }

        return `<div class="log-entry ${statusClass}">${content}</div>`;
    }).join('');

    console.log(`DEBUG: Generated HTML for ${logId}:`, htmlContent);
    console.log("Final HTML content:", htmlContent);
    logElement.innerHTML = htmlContent;
    logElement.scrollTop = logElement.scrollHeight;

    if (queue.size() > MAX_VISIBLE_ITEMS) {
        const overflowText = `+${queue.size() - MAX_VISIBLE_ITEMS} more items`;
        console.log("Adding overflow indicator:", overflowText);
        logElement.innerHTML += `<div class="log-overflow">${overflowText}</div>`;
    }

    console.log("Log updated successfully");
    console.groupEnd();
}

export function updateQueueCounters() {
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
