// Frontend/src/modules/QueueDisplay.js (UPDATED: Delayed DOM access)

let uiComponentRef = null; // This will hold the reference to the Lit UI component instance

/**
 * Sets the reference to the main UI component instance.
 * This should be called by app.js after the UI component has rendered.
 * @param {Object} component - The main UI component (ElectronMyElement) instance.
 */
const setUIDomElements = (component) => {
    uiComponentRef = component;
    console.log('QueueDisplay: UI component instance set.');
    // No need to query elements here. The update functions will query on demand.
};

// Helper function to safely get a DOM element from the UI component's shadowRoot
const getElement = (id) => {
    if (!uiComponentRef || !uiComponentRef.shadowRoot) {
        // console.warn(`QueueDisplay: UI component reference or shadowRoot not available yet for element '${id}'.`);
        return null;
    }
    return uiComponentRef.shadowRoot.getElementById(id);
};


const updateLog = (logId, message, logName) => {
    const logElement = getElement(logId);
    if (logElement) {
        // Only append to the DOM element if it exists
        const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
        logElement.value += `[${timestamp}] ${message}\n`;
        logElement.scrollTop = logElement.scrollHeight; // Auto-scroll to bottom
    } else {
        // If the element is not yet in the DOM (e.g., during very early init), log to console instead
        console.log(`[${logName} - (UI not ready for ${logId})]: ${message}`);
    }
};

const updateSystemLog = (message) => {
    updateLog('systemLog', message, 'System Log');
};

const updateStatusLog = (message) => {
    updateLog('statusLog', message, 'Status Log');
};

const updateTestLog = (message) => {
    updateLog('testLog', message, 'Test Log');
};

const updateSimulationLog = (message) => {
    let logMessage;
    if (typeof message === 'object' && message !== null) {
        logMessage = `Status: ${message.status || 'N/A'}, Progress: ${message.progress || 'N/A'}, Message: ${message.message || 'N/A'}`;
    } else {
        logMessage = message;
    }
    updateLog('simulationLog', logMessage, 'Simulation Log');
};

const updateTranscriptionLog = (message) => {
    updateLog('transcriptionLog', message, 'Transcription Log');
};


const updateQueueDisplay = (queueName, size, items = []) => {
    let displayElementId;
    let queueDisplayName;

    // Map backend queue names to frontend display IDs if necessary
    // Ensure these IDs match the IDs in your ui.js render method
    if (queueName === 'toBackendQueue') { // Frontend's internal name for outbound queue
        displayElementId = 'frontendOutgoingQueueDisplay';
        queueDisplayName = 'Frontend Outgoing Queue';
    } else if (queueName === 'fromBackendQueue') { // Frontend's internal name for inbound queue
        displayElementId = 'frontendIncomingQueueDisplay';
        queueDisplayName = 'Frontend Incoming Queue';
    } else if (queueName === 'dead_letter_queue' || queueName === 'deadLetterQueue') { // Backend's dead letter queue
        displayElementId = 'deadLetterQueueDisplay';
        queueDisplayName = 'Backend Dead Letter Queue';
    } else if (queueName === 'from_frontend_queue') { // Backend's 'from_frontend_queue' which is frontend's outbound queue on backend
         // This is a status update *from the backend* about its queue.
         // It represents the queue on the backend that receives messages from the frontend.
         // We should update the *frontend's outgoing queue display* based on the backend's perspective.
        displayElementId = 'frontendOutgoingQueueDisplay'; // Update FE outgoing display
        queueDisplayName = 'Backend (FE Outbound) Queue';
    } else if (queueName === 'to_frontend_queue') { // Backend's 'to_frontend_queue' which is frontend's inbound queue on backend
         // This is a status update *from the backend* about its queue.
         // It represents the queue on the backend that sends messages to the frontend.
         // We should update the *frontend's incoming queue display* based on the backend's perspective.
        displayElementId = 'frontendIncomingQueueDisplay'; // Update FE incoming display
        queueDisplayName = 'Backend (FE Inbound) Queue';
    } else {
        console.warn(`QueueDisplay: Unknown queue name for display: ${queueName}`);
        return;
    }

    const sizeElement = getElement(displayElementId);

    if (sizeElement) {
        sizeElement.textContent = size.toString();
        // You might extend this to show `items` as well, e.g., in a popup or expanded view
        // For now, just logging if items are passed for debugging
        if (items && items.length > 0) {
            console.debug(`QueueDisplay: ${queueDisplayName} items:`, items);
        }
    } else {
        console.warn(`QueueDisplay: Display element with ID "${displayElementId}" not found in the DOM for queue "${queueName}".`);
    }
};

export {
    updateSystemLog,
    updateStatusLog,
    updateTestLog,
    updateSimulationLog,
    updateTranscriptionLog,
    updateQueueDisplay,
    setUIDomElements // Export the setter function
};