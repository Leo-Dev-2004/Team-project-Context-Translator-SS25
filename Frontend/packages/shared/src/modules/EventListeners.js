// Frontend/src/modules/EventListeners.js

import { updateSystemLog, updateStatusLog, updateSimulationLog, updateTestLog, updateTranscriptionLog } from './QueueDisplay.js';
import { WebSocketManager } from './WebSocketManager.js';
import { MessageQueue } from './MessageQueue.js';
import { MessagingService } from './MessagingService.js';

let fromBackendQueue;
let frontendDisplayQueue;
let webSocketManager;
let uiComponent; // Reference to the UI component instance (ElectronMyElement)
let translateButton; // Global reference for the translate button
let startSimButton; // Global reference for the start simulation button
let stopSimButton;  // Global reference for the stop simulation button

let isWebSocketReady = false; // Tracks if WebSocket is ready for sending/receiving

/**
 * Sets the WebSocket ready state and updates UI button disabled states accordingly.
 * @param {boolean} state - True if WebSocket is ready, false otherwise.
 */
const setWebSocketReadyState = (state) => {
    isWebSocketReady = state;
    // Query buttons from the UI component's shadowRoot for their current state
    // These should be consistently accessed from the uiComponent's shadowRoot
    const translateBtn = uiComponent?.shadowRoot?.getElementById('translateText');
    const startSimBtn = uiComponent?.shadowRoot?.getElementById('startSimulation');
    const stopSimBtn = uiComponent?.shadowRoot?.getElementById('stopSimulation');

    if (translateBtn) translateBtn.disabled = !state;
    if (startSimBtn) startSimBtn.disabled = !state;
    if (stopSimBtn) stopSimBtn.disabled = !state;
    console.log(`EventListeners: WebSocket ready state set to ${state}. UI buttons updated.`);
};

/**
 * Sets the references to the MessageQueues, WebSocketManager, and the UI component instance.
 * This function should be called once during application initialization.
 * @param {Object} queues - An object containing references to the MessageQueue instances.
 * @param {Object} manager - The WebSocketManager singleton instance.
 * @param {Object} component - The main UI component (ElectronMyElement) instance.
 */
const setQueuesAndManager = (queues, manager, component) => {
    if (!queues || !manager || !component) {
        console.error('EventListeners: setQueuesAndManager received null/undefined queues, manager, or component. Cannot proceed.');
        return;
    }
    webSocketManager = manager;
    fromBackendQueue = queues.fromBackendQueue;
    frontendDisplayQueue = queues.frontendDisplayQueue;
    uiComponent = component; // Assign the UI component instance
    console.log('EventListeners: Queues, WebSocketManager, and UI component references set.');

    // Start processing messages from the frontend display queue immediately
    processFrontendDisplayQueueMessages();
};

/**
 * Initializes all necessary UI event listeners.
 * This should be called after the UI component has rendered and its elements are available.
 */
const initializeEventListeners = () => {
    // Query DOM elements from the UI component's shadowRoot after the UI is rendered
    // These assignments are safe because uiComponent is already set by app.js before this function is called.
    translateButton = uiComponent?.shadowRoot?.getElementById('translateText');
    const sourceText = uiComponent?.shadowRoot?.getElementById('sourceText');
    const clearTextButton = uiComponent?.shadowRoot?.getElementById('clearText');
    const saveSettingsButton = uiComponent?.shadowRoot?.getElementById('saveSettings');
    const translationMode = uiComponent?.shadowRoot?.getElementById('translationMode'); // Assuming this is an md-select element
    const contextLevel = uiComponent?.shadowRoot?.getElementById('contextLevel');     // Assuming this is an md-select element
    startSimButton = uiComponent?.shadowRoot?.getElementById('startSimulation');
    stopSimButton = uiComponent?.shadowRoot?.getElementById('stopSimulation');

    // Ensure buttons are initially disabled until connected
    if (translateButton) translateButton.disabled = true;
    if (startSimButton) startSimButton.disabled = true;
    if (stopSimButton) stopSimButton.disabled = true;

    // --- UI Event Listeners ---
    if (translateButton) {
        translateButton.addEventListener('click', () => {
            const text = sourceText?.value; // Use optional chaining for sourceText
            if (!text || text.trim() === '') {
                updateSystemLog('Source text is empty. Cannot translate.');
                return;
            }
            if (!webSocketManager || !webSocketManager.isConnected()) {
                updateSystemLog('Not connected to backend. Cannot send translation request.');
                return;
            }
            translateButton.disabled = true; // Disable button immediately
            const translationLoading = uiComponent?.shadowRoot?.getElementById('translationLoading');
            if (translationLoading) translationLoading.classList.remove('hidden');

            MessagingService.sendToBackend(
                'translation_request',
                { text: text, mode: translationMode?.value, context_level: parseInt(contextLevel?.value) } // Use optional chaining for select values
            );
            updateSystemLog('Translation request sent.');
        });
    } else {
        console.warn('EventListeners: translateButton not found in DOM.');
    }

    if (clearTextButton) {
        clearTextButton.addEventListener('click', () => {
            if (sourceText) sourceText.value = '';
            const translationOutput = uiComponent?.shadowRoot?.getElementById('translationOutput');
            if (translationOutput) translationOutput.textContent = '';
            updateSystemLog('Text cleared.');
        });
    } else {
        console.warn('EventListeners: clearTextButton not found in DOM.');
    }

    if (saveSettingsButton) {
        saveSettingsButton.addEventListener('click', () => {
            if (!webSocketManager || !webSocketManager.isConnected()) {
                updateSystemLog('Not connected to backend. Cannot save settings.');
                return;
            }
            MessagingService.sendToBackend(
                'update_settings',
                {
                    mode: translationMode?.value, // Use optional chaining
                    context_level: parseInt(contextLevel?.value) // Use optional chaining
                }
            );
            updateSystemLog('Settings update request sent.');
        });
    } else {
        console.warn('EventListeners: saveSettingsButton not found in DOM.');
    }

    if (startSimButton) {
        startSimButton.addEventListener('click', () => {
            if (!webSocketManager || !webSocketManager.isConnected()) {
                updateSystemLog('Not connected to backend. Cannot start simulation.');
                return;
            }
            MessagingService.sendToBackend('start_simulation', { message: 'Start simulation' });
            updateSystemLog('Start simulation request sent.');
            startSimButton.disabled = true;
            if (stopSimButton) stopSimButton.disabled = false; // Ensure stop is enabled
        });
    } else {
        console.warn('EventListeners: startSimButton not found in DOM.');
    }

    if (stopSimButton) {
        stopSimButton.addEventListener('click', () => {
            if (!webSocketManager || !webSocketManager.isConnected()) {
                updateSystemLog('Not connected to backend. Cannot stop simulation.');
                return;
            }
            MessagingService.sendToBackend('stop_simulation', { message: 'Stop simulation' });
            updateSystemLog('Stop simulation request sent.');
            stopSimButton.disabled = true;
            if (startSimButton) startSimButton.disabled = false; // Ensure start is enabled
        });
    } else {
        console.warn('EventListeners: stopSimButton not found in DOM.');
    }
    console.log('EventListeners: UI event listeners set up.');
};

/**
 * Processes messages from the frontend display queue, updating the UI accordingly.
 * This function runs in an infinite loop as long as `_running` is true.
 */
async function processFrontendDisplayQueueMessages() {
    if (processFrontendDisplayQueueMessages._running) {
        console.warn('FrontendDisplayQueue Processor: Loop already running. Preventing duplicate.');
        return;
    }
    processFrontendDisplayQueueMessages._running = true;
    console.group('FrontendDisplayQueue Processor: Starting message processing loop...');
    updateSystemLog('Frontend display message processing loop started.');

    try {
        while (processFrontendDisplayQueueMessages._running) {
            if (!frontendDisplayQueue) {
                console.warn('FrontendDisplayQueue Processor: frontendDisplayQueue not initialized. Waiting...');
                await new Promise(resolve => setTimeout(resolve, 500)); // Wait before re-checking
                continue;
            }
            const message = await frontendDisplayQueue.dequeue(); // Dequeue a message (waits if queue is empty)

            // Introduce a small delay to prevent UI freezing on rapid updates
            await new Promise(resolve => setTimeout(resolve, 100));

            if (message) {
                console.log('FrontendDisplayQueue Processor: Dequeued message for display:', message.type, message.payload);

                // Use optional chaining for all uiComponent?.shadowRoot?.getElementById calls
                // and handle cases where elements might not be found.
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        const connectionStatusElement = uiComponent?.shadowRoot?.getElementById('connectionStatus');
                        if (connectionStatusElement) connectionStatusElement.textContent = 'Connected (Acknowledged)';
                        setWebSocketReadyState(true);
                        updateSystemLog(`Connection acknowledged by backend. Client ID: ${message.data.client_id}`);
                        break;
                    case 'backend_ready_confirm':
                        updateStatusLog(`Backend Ready: ${message.payload.message}`);
                        break;
                    case 'system_info':
                        console.log('MessageProcessor: System message received:', message.payload);
                        const simulationStatusElement = uiComponent?.shadowRoot?.getElementById('simulationStatus');
                        if (simulationStatusElement) simulationStatusElement.textContent = message.payload.message;
                        updateSystemLog(message.payload.message);
                        break;
                    case 'simulation_update':
                        console.log('MessageProcessor: Simulation update received:', message.payload);
                        updateSimulationLog(message.payload);
                        break;
                    case 'status_update':
                        console.log('MessageProcessor: Status update received:', message.payload);
                        const statusLogMessage = `Status: ${message.payload.original_type || 'unknown'} processed (ID: ${message.payload.id || message.payload.original_id || 'N/A'})`;
                        updateStatusLog(statusLogMessage);
                        if (message.payload.original_type === 'translation_request' && translateButton) {
                            translateButton.disabled = false;
                            const translationLoading = uiComponent?.shadowRoot?.getElementById('translationLoading');
                            if (translationLoading) translationLoading.classList.add('hidden');
                        }
                        break;
                    case 'test_message_response':
                        console.log('MessageProcessor: Test message received (backend response):', message.payload);
                        updateTestLog(`Test Message Response: ${message.payload.content || message.payload.text || JSON.stringify(message.payload)}`);
                        break;
                    case 'simulation_status_update':
                        console.log('MessageProcessor: Simulation status update received:', message.payload);
                        updateSimulationLog(message.payload);
                        if (message.payload.status === 'started') {
                            if (startSimButton) {
                                startSimButton.disabled = true;
                                startSimButton.textContent = 'Running';
                            }
                            if (stopSimButton) stopSimButton.disabled = false;
                        } else if (message.payload.status === 'stopped') {
                            if (startSimButton) {
                                startSimButton.disabled = false;
                                startSimButton.textContent = 'Start Simulation';
                            }
                            if (stopSimButton) stopSimButton.disabled = true;
                        }
                        break;
                    case 'agent_log':
                        console.log('MessageProcessor: Agent log received:', message.payload);
                        updateSystemLog(`Agent Log: ${JSON.stringify(message.payload)}`);
                        break;
                    case 'queue_status_update':
                        // This case is primarily handled by WebSocketManager directly calling updateQueueDisplay
                        // but if it ever ends up here, just log for debugging.
                        console.log('MessageProcessor: Queue status update received via display queue. (Should be handled directly by WSManager)');
                        break;
                    case 'status': // Generic status message from backend
                        if (message.payload.status === 'simulation_initiated') {
                            console.log('MessageProcessor: Simulation initiated (backend status):', message.payload);
                            const simulationStatusElement = uiComponent?.shadowRoot?.getElementById('simulationStatus');
                            if (simulationStatusElement) simulationStatusElement.textContent = 'Running';
                            updateSystemLog(`Simulation: ${message.payload.message || 'Started'}`);
                            if (startSimButton) {
                                startSimButton.disabled = true;
                                startSimButton.textContent = 'Running';
                            }
                            if (stopSimButton) stopSimButton.disabled = false;
                        } else if (message.payload.status === 'simulation_stopped') {
                            console.log('MessageProcessor: Simulation stopped (backend status):', message.payload);
                            const simulationStatusElement = uiComponent?.shadowRoot?.getElementById('simulationStatus');
                            if (simulationStatusElement) simulationStatusElement.textContent = 'Stopped';
                            updateSystemLog(`Simulation: ${message.payload.message || 'Stopped'}`);
                            if (startSimButton) {
                                startSimButton.disabled = false;
                                startSimButton.textContent = 'Start Simulation';
                            }
                            if (stopSimButton) stopSimButton.disabled = true;
                        } else {
                            console.log('MessageProcessor: Generic status message:', message.payload);
                            updateStatusLog(`Status: ${JSON.stringify(message.payload)}`);
                        }
                        break;
                    case 'frontend_ready_ack':
                        console.log('MessageProcessor: Backend acknowledged frontend readiness.');
                        updateSystemLog(`Backend: Frontend ready acknowledged.`);
                        break;
                    case 'transcription_result':
                        console.log('MessageProcessor: Transcription result received:', message.payload);
                        updateTranscriptionLog(message.payload.text || JSON.stringify(message.payload));
                        break;
                    case 'data': // This is typically for translated text results
                        console.log('MessageProcessor: Data/result received:', message.payload);
                        const translationOutputElement = uiComponent?.shadowRoot?.getElementById('translationOutput');
                        if (translationOutputElement) translationOutputElement.textContent = message.payload.translated_text || JSON.stringify(message.payload, null, 2);
                        const translationLoading = uiComponent?.shadowRoot?.getElementById('translationLoading');
                        if (translationLoading) {
                            translationLoading.classList.add('hidden');
                        }
                        if (translateButton) translateButton.disabled = false; // Re-enable translate button
                        break;
                    case 'settings_updated_ack':
                        updateStatusLog(`Backend confirmed settings update: ${JSON.stringify(message.payload)}`);
                        console.log('Backend confirmed settings update:', message.payload);
                        break;
                    case 'ping':
                        console.log('Frontend received ping from backend:', message);
                        break;
                    case 'pong':
                        console.log('Frontend received pong from backend:', message);
                        break;
                    case 'system_heartbeat':
                         console.log('Frontend received heartbeat from backend:', message);
                         updateSystemLog('Backend Heartbeat received.');
                         break;
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type, message);
                        updateSystemLog(`Unknown message type: ${message.type} - ${JSON.stringify(message.payload || {}).substring(0,100)}...`);
                }
            }
        }
    } catch (error) {
        console.error('FrontendDisplayQueue Processor: Fatal error in message processing loop:', error);
        updateSystemLog(`Fatal error in frontend display processor: ${error.message}`);
    } finally {
        console.groupEnd();
        processFrontendDisplayQueueMessages._running = false;
        console.log('FrontendDisplayQueue Processor: Message processing loop stopped.');
        updateSystemLog('Frontend display message processing loop stopped.');
    }
}

export { initializeEventListeners, setWebSocketReadyState, setQueuesAndManager };