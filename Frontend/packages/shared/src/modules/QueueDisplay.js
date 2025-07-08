// Frontend/src/modules/QueueDisplay.js (MODIFIED to accept UI component instance)

let uiComponentRef = null; // Store a reference to the UI component

export const setUIDomElements = (component) => { // <--- NEW METHOD
    uiComponentRef = component;
    console.log('QueueDisplay: UI component instance set.');
};

export const updateSystemLog = (message) => {
    // Query from the UI component's shadowRoot/light DOM
    const logElement = uiComponentRef?.shadowRoot?.getElementById('systemLog') || document.getElementById('systemLog');
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        logElement.textContent += `[${timestamp}] ${message}\n`;
        logElement.scrollTop = logElement.scrollHeight; // Auto-scroll to bottom
    } else {
        console.warn('QueueDisplay: systemLog element not found.');
        console.log(`[System Log]: ${message}`); // Fallback to console
    }
};

export const updateStatusLog = (message) => {
    const logElement = uiComponentRef?.shadowRoot?.getElementById('statusLog') || document.getElementById('statusLog');
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        logElement.textContent += `[${timestamp}] ${message}\n`;
        logElement.scrollTop = logElement.scrollHeight;
    } else {
        console.warn('QueueDisplay: statusLog element not found.');
        console.log(`[Status Log]: ${message}`);
    }
};

export const updateSimulationLog = (payload) => {
    const logElement = uiComponentRef?.shadowRoot?.getElementById('simulationLog') || document.getElementById('simulationLog');
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        const message = payload.message || JSON.stringify(payload);
        logElement.textContent += `[${timestamp}] ${message}\n`;
        logElement.scrollTop = logElement.scrollHeight;
    } else {
        console.warn('QueueDisplay: simulationLog element not found.');
        console.log(`[Simulation Log]: ${payload.message || JSON.stringify(payload)}`);
    }
};

export const updateTestLog = (message) => {
    const logElement = uiComponentRef?.shadowRoot?.getElementById('testLog') || document.getElementById('testLog');
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        logElement.textContent += `[${timestamp}] ${message}\n`;
        logElement.scrollTop = logElement.scrollHeight;
    } else {
        console.warn('QueueDisplay: testLog element not found.');
        console.log(`[Test Log]: ${message}`);
    }
};

export const updateTranscriptionLog = (text) => {
    const logElement = uiComponentRef?.shadowRoot?.getElementById('transcriptionLog') || document.getElementById('transcriptionLog');
    const sourceTextElement = uiComponentRef?.shadowRoot?.getElementById('sourceText') || document.getElementById('sourceText'); // Also update sourceText
    
    if (logElement) {
        const timestamp = new Date().toLocaleTimeString();
        logElement.textContent += `[${timestamp}] ${text}\n`;
        logElement.scrollTop = logElement.scrollHeight;
    } else {
        console.warn('QueueDisplay: transcriptionLog element not found.');
        console.log(`[Transcription Log]: ${text}`);
    }

    if (sourceTextElement) {
        sourceTextElement.value = text; // Update the source text field with transcription
    } else {
        console.warn('QueueDisplay: sourceText element not found.');
    }
};

// This function is called by WebSocketManager to update queue sizes
export const updateQueueDisplay = (queueName, size, items) => {
    let displayElementId;
    // Map the internal queue names to their display element IDs
    if (queueName === 'toBackendQueue') {
        displayElementId = 'frontendOutgoingQueueDisplay';
    } else if (queueName === 'fromBackendQueue') {
        displayElementId = 'frontendIncomingQueueDisplay';
    } else if (queueName === 'dead_letter_queue') {
        displayElementId = 'deadLetterQueueDisplay'; // Assuming you have this ID for backend DLQ
    } else if (queueName === 'from_frontend_queue') { // Backend's perspective of frontend's outgoing
        displayElementId = 'frontendOutgoingQueueDisplay'; // Map to frontend's outgoing
    } else if (queueName === 'to_frontend_queue') { // Backend's perspective of frontend's incoming
        displayElementId = 'frontendIncomingQueueDisplay'; // Map to frontend's incoming
    } else {
        console.warn(`QueueDisplay: Unknown queue name for display: ${queueName}`);
        return;
    }

    const element = uiComponentRef?.shadowRoot?.getElementById(displayElementId) || document.getElementById(displayElementId);
    if (element) {
        element.textContent = size.toString();
    } else {
        console.warn(`QueueDisplay: Display element with ID "${displayElementId}" not found in the DOM for queue "${queueName}".`);
    }
};