// frontend/src/modules/EventListeners.js

import { WebSocketManager } from './WebSocketManager.js'; // Imports the singleton instance
import {
    updateSystemLog,
    updateStatusLog,
    updateTestLog,
    updateSimulationLog,
    updateTranscriptionLog, // Added for explicit transcription log
    updateQueueDisplay // Needed if we want to explicitly update all queues
} from './QueueDisplay.js';

let toBackendQueue;
let fromBackendQueue; // This is the crucial queue for incoming messages
let frontendDisplayQueue;
let frontendActionQueue;

let webSocketManagerInstance; // This will hold the singleton instance passed from app.js

let isWebSocketReady = false; // Initial state: not ready

// Declare button references globally but assign them inside initializeEventListeners
// after DOM is loaded. This makes them accessible to enable/disable functions.
let startSimButton;
let stopSimButton;
let sendTestMessageButton;
let sendTranscriptionButton;
let translateButton; // Added for completeness
let clearButton; // Added for completeness
let saveSettingsButton; // Added for completeness
let sourceTextArea; // Added for completeness
let translationModeSelect; // Added for completeness
let contextLevelSlider; // Added for completeness


/**
 * Sets the queue instances and WebSocketManager from app.js.
 * This should be called once during application initialization.
 * @param {Object} queues - Object containing references to MessageQueue instances.
 * @param {WebSocketManager} manager - The WebSocketManager singleton instance.
 */
export function setupEventListeners({
    webSocketManager,
    frontendActionQueue,
    toBackendQueue: appToBackendQueue, // Rename to avoid confusion with local `toBackendQueue` variable
    fromBackendQueue: appFromBackendQueue, // Rename to avoid confusion with local `fromBackendQueue` variable
    frontendDisplayQueue: appFrontendDisplayQueue
}) {
    // Assign global variables from the passed arguments
    toBackendQueue = appToBackendQueue;
    fromBackendQueue = appFromBackendQueue;
    frontendDisplayQueue = appFrontendDisplayQueue;
    frontendActionQueue = frontendActionQueue; // This was correctly passed
    webSocketManagerInstance = webSocketManager;
    console.log('EventListeners: Queues and WebSocketManager assigned.');

    // Start the message processing loop only once the WebSocketManager is ready
    // and queues are set up.
    if (!processBackendMessages._started) {
        processBackendMessages._started = true;
        processBackendMessages();
    }
}


function disableActionButtons() {
    console.log('EventListeners: Disabling action buttons.');
    // Check if elements are assigned before trying to disable
    if (startSimButton) startSimButton.disabled = true;
    if (stopSimButton) stopSimButton.disabled = true;
    if (sendTestMessageButton) sendTestMessageButton.disabled = true;
    if (sendTranscriptionButton) sendTranscriptionButton.disabled = true;
    if (translateButton) translateButton.disabled = true; // Disable translate button too
    if (saveSettingsButton) saveSettingsButton.disabled = true; // Disable save settings
    updateSystemLog('Action buttons disabled (waiting for WebSocket connection).');
}

function enableActionButtons() {
    console.log('EventListeners: Enabling action buttons.');
    // Check if elements are assigned before trying to enable
    if (startSimButton) {
        startSimButton.disabled = false;
        startSimButton.textContent = 'Start Simulation'; // Reset text
    }
    if (stopSimButton) stopSimButton.disabled = false;
    if (sendTestMessageButton) sendTestMessageButton.disabled = false;
    if (sendTranscriptionButton) sendTranscriptionButton.disabled = false;
    if (translateButton) translateButton.disabled = false; // Enable translate button
    if (saveSettingsButton) saveSettingsButton.disabled = false; // Enable save settings
    updateSystemLog('Action buttons enabled (WebSocket connection ready).');
}

// Public method to set WebSocket readiness
export function setWebSocketReadyState(state) {
    console.log(`EventListeners: setWebSocketReadyState called with state: ${state}. Current is: ${isWebSocketReady}`);
    if (isWebSocketReady === state) {
        // Prevent redundant calls if state hasn't changed
        return;
    }
    isWebSocketReady = state;
    if (isWebSocketReady) {
        enableActionButtons();
        console.log('EventListeners: WebSocket fully initialized and acknowledged by server.');
    } else {
        disableActionButtons();
        console.log('EventListeners: WebSocket not ready.');
    }
}


export function initializeEventListeners() {
    console.log('EventListeners: Initializing...');

    // Assign button references (ensure these IDs match your HTML)
    translateButton = document.getElementById('translateText');
    clearButton = document.getElementById('clearText');
    saveSettingsButton = document.getElementById('saveSettings');
    sourceTextArea = document.getElementById('sourceText');
    translationModeSelect = document.getElementById('translationMode');
    contextLevelSlider = document.getElementById('contextLevel');
    startSimButton = document.getElementById('startSimButton');
    stopSimButton = document.getElementById('stopSimButton');
    sendTestMessageButton = document.getElementById('sendTestMessageButton');
    sendTranscriptionButton = document.getElementById('sendTranscriptionButton');


    // Translation handler
    if (translateButton) {
        translateButton.addEventListener('click', () => {
            const text = sourceTextArea.value.trim();
            if (!text) {
                updateSystemLog('Error: No text to translate');
                return;
            }

            if (!isWebSocketReady) {
                updateSystemLog('Error: WebSocket not ready');
                return;
            }

            // Show loading state
            const translationLoading = document.getElementById('translationLoading');
            if (translationLoading) {
                translationLoading.classList.remove('hidden');
            }
            translateButton.disabled = true; // Disable until response

            const translationId = `trans_${Date.now()}`;
            const mode = translationModeSelect.value;
            const contextLevel = contextLevelSlider.value;

            webSocketManagerInstance.sendMessage({
                type: 'translation_request',
                id: translationId,
                data: {
                    text,
                    mode,
                    context_level: parseInt(contextLevel),
                    timestamp: new Date().toISOString()
                }
            });

            updateSystemLog(`Sent translation request (ID: ${translationId})`);
        });
    }

    // Clear text handler
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            sourceTextArea.value = '';
            document.getElementById('translationOutput').textContent = '';
        });
    }

    // Settings handler
    if (saveSettingsButton) {
        saveSettingsButton.addEventListener('click', () => {
            if (!isWebSocketReady) {
                updateSystemLog('Error: WebSocket not ready. Cannot save settings.');
                return;
            }

            const mode = translationModeSelect.value;
            const contextLevel = contextLevelSlider.value;

            webSocketManagerInstance.sendMessage({
                type: 'command',
                data: {
                    command: 'set_translation_settings',
                    mode,
                    context_level: parseInt(contextLevel)
                },
                timestamp: Date.now() // Add timestamp for consistency
            });

            updateSystemLog(`Updated translation settings: Mode=${mode}, Context=${contextLevel}`);
        });
    }

    // Initially disable all action buttons (this ensures they are disabled immediately on page load)
    disableActionButtons();

    // Add event listeners for simulation and test messages
    if (startSimButton) {
        startSimButton.addEventListener('click', () => {
            console.log('EventListeners: startSim button clicked.');
            if (isWebSocketReady) {
                const commandId = `cmd_${Date.now()}`;
                updateSystemLog(`Sending start_simulation command (ID: ${commandId})`);

                webSocketManagerInstance.sendMessage({
                    type: 'command',
                    id: commandId,
                    data: {
                        command: 'start_simulation',
                        parameters: {} // Can add parameters here
                    },
                    timestamp: Date.now()
                });

                // Disable button and change text until response received
                startSimButton.disabled = true;
                startSimButton.textContent = 'Starting...';
                console.log('EventListeners: startSim button clicked, command sent.');
            } else {
                console.warn('EventListeners: WebSocket not open. Command not sent: start_simulation');
                updateSystemLog('Error: WebSocket not open. Cannot start simulation.');
            }
        });
    }

    if (stopSimButton) {
        stopSimButton.addEventListener('click', () => {
            console.log('EventListeners: stopSim button clicked.');
            if (isWebSocketReady) {
                const commandId = `cmd_${Date.now()}`; // Add a unique ID for stop command
                updateSystemLog('User clicked: Stop Simulation');
                webSocketManagerInstance.sendMessage({
                    type: 'command',
                    id: commandId,
                    data: {
                        command: 'stop_simulation'
                    },
                    timestamp: Date.now()
                });
                console.log('EventListeners: stopSim button clicked, command sent.');
            } else {
                console.warn('EventListeners: WebSocket not open. Command not sent: stop_simulation');
                updateSystemLog('Error: WebSocket not open. Cannot stop simulation.');
            }
        });
    }

    if (sendTestMessageButton) {
        sendTestMessageButton.addEventListener('click', () => {
            if (isWebSocketReady) {
                sendTestMessage();
            } else {
                console.warn('EventListeners: WebSocket not open. Cannot send test message.');
                updateSystemLog('Error: WebSocket not open. Cannot send test message.');
            }
        });
    }

    if (sendTranscriptionButton) {
        sendTranscriptionButton.addEventListener('click', () => {
            if (isWebSocketReady) {
                const transcriptionInput = document.getElementById('transcriptionInput');
                if (transcriptionInput && transcriptionInput.value.trim() !== "") {
                    webSocketManagerInstance.sendMessage({
                        type: 'transcription',
                        id: `transcribe_${Date.now()}`, // Add unique ID
                        data: {
                            text: transcriptionInput.value.trim()
                        },
                        timestamp: Date.now()
                    });
                    updateSystemLog(`Transcription Sent: "${transcriptionInput.value.trim().substring(0, 50)}..."`);
                    transcriptionInput.value = '';
                } else {
                    updateSystemLog("Transcription input is empty.");
                }
            } else {
                console.warn('EventListeners: WebSocket not open. Cannot send transcription.');
                updateSystemLog('Error: WebSocket not open. Cannot send transcription.');
            }
        });
    }

    console.log('EventListeners: Buttons assigned and listeners attached.');
    console.log('EventListeners: Initialization complete.');
}

function sendTestMessage() {
    console.log('TRACE: sendTestMessage called!');
    const testMessage = {
        type: 'test_message',
        data: {
            text: `Hello from frontend! (Timestamp: ${new Date().toLocaleTimeString()})`,
            value: 123
        },
        timestamp: Date.now(),
        id: `test-${Date.now()}` // Ensure ID is a string for consistency
    };
    console.log("DEBUG: Prepared test message:", testMessage);
    webSocketManagerInstance.sendMessage(testMessage);
    console.log("DEBUG: sendTestMessage completed, message passed to WebSocketManager.");

    updateSystemLog('Sent Test Message to Backend');
}

// Function to update all relevant queue displays manually
function updateAllQueueDisplays() {
    if (toBackendQueue) {
        updateQueueDisplay(toBackendQueue.name, toBackendQueue.size(), toBackendQueue.getCurrentItemsForDisplay());
    }
    if (fromBackendQueue) {
        updateQueueDisplay(fromBackendQueue.name, fromBackendQueue.size(), fromBackendQueue.getCurrentItemsForDisplay());
    }
    if (frontendDisplayQueue) {
        updateQueueDisplay(frontendDisplayQueue.name, frontendDisplayQueue.size(), frontendDisplayQueue.getCurrentItemsForDisplay());
    }
    if (frontendActionQueue) {
        updateQueueDisplay(frontendActionQueue.name, frontendActionQueue.size(), frontendActionQueue.getCurrentItemsForDisplay());
    }
    // Note: Backend queue updates are handled by WebSocketManager directly on 'queue_status_update' messages.
}

/**
 * Initiates and manages the message processing loop for messages from the backend.
 * This loop continuously dequeues messages from `fromBackendQueue` and processes them.
 */
export async function processBackendMessages() {
    if (processBackendMessages._running) {
        console.warn('MessageProcessor: Loop already running. Preventing duplicate.');
        return;
    }
    processBackendMessages._running = true;
    console.group('MessageProcessor: Starting message processing loop...');
    updateSystemLog('Message processing loop started.');

    try {
        while (processBackendMessages._running) { // Loop until explicitly stopped
            // Only dequeue if WebSocket is ready. Otherwise, pause dequeuing.
            if (!isWebSocketReady) {
                // If not ready, wait a bit and check again without dequeuing
                await new Promise(resolve => setTimeout(resolve, 500)); // Longer wait if not ready
                continue;
            }

            // Dequeue a message. This will wait if the queue is empty.
            const message = await fromBackendQueue.dequeue();

            // If message is null, it means the queue was cleared while waiting,
            // or there was an issue. We should continue the loop.
            if (message === null) {
                continue; // Continue waiting for valid messages
            }

            console.log('MessageProcessor: Dequeued message from backend:', message);
            // Simulate processing delay (optional)
            await new Promise(resolve => setTimeout(resolve, 10));

            try {
                // This switch statement now directly processes messages consumed from fromBackendQueue.
                // The appObserver in app.js (which WebSocketManager uses) should primarily
                // enqueue messages into fromBackendQueue and update general logs.
                // This module then processes specific message types that affect UI state.
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected (Acknowledged)';
                        // WebSocketReady state should be set by WebSocketManager's onopen or an initial ACK
                        // We'll keep it here for now to ensure buttons enable after initial connection.
                        setWebSocketReadyState(true);
                        updateSystemLog(`Connection acknowledged by backend. Client ID: ${message.data.client_id}`);
                        break;
                    case 'backend_ready_confirm': // Backend's confirmation that it's ready
                        updateStatusLog(`Backend Ready: ${message.data.message}`);
                        break;
                    case 'system_info':
                        console.log('MessageProcessor: System message received:', message.data);
                        document.getElementById('simulationStatus').textContent = message.data.message;
                        updateSystemLog(message.data.message);
                        break;
                    case 'simulation_update':
                        console.log('MessageProcessor: Simulation update received:', message.data);
                        updateSimulationLog(message.data);
                        break;
                    case 'status_update': // Generic status update
                        console.log('MessageProcessor: Status update received:', message.data);
                        const statusLogMessage = `Status: ${message.data.original_type || 'unknown'} processed (ID: ${message.data.id || message.data.original_id || 'N/A'})`;
                        updateStatusLog(statusLogMessage);
                        // Re-enable translate button after translation_request is processed
                        if (message.data.original_type === 'translation_request' && translateButton) {
                            translateButton.disabled = false;
                            const translationLoading = document.getElementById('translationLoading');
                            if (translationLoading) {
                                translationLoading.classList.add('hidden');
                            }
                        }
                        break;
                    case 'test_message_response': // Assuming backend sends this for 'test_message'
                        console.log('MessageProcessor: Test message received (backend response):', message.data);
                        updateTestLog(`Test Message Response: ${message.data.content || message.data.text || JSON.stringify(message.data)}`);
                        break;
                    case 'simulation_status_update': // This type is often from backend for sim status
                        console.log('MessageProcessor: Simulation status update received:', message.data);
                        updateSimulationLog(message.data);
                        // Handle button re-enabling based on sim status
                        if (message.data.status === 'started' && startSimButton) {
                            startSimButton.disabled = false; // Or disable if it's already running
                            startSimButton.textContent = 'Running';
                            stopSimButton.disabled = false;
                        } else if (message.data.status === 'stopped' && startSimButton) {
                            startSimButton.disabled = false;
                            startSimButton.textContent = 'Start Simulation';
                            stopSimButton.disabled = true;
                        }
                        break;
                    case 'agent_log':
                        console.log('MessageProcessor: Agent log received:', message.data);
                        updateSystemLog(`Agent Log: ${JSON.stringify(message.data)}`);
                        break;
                    case 'queue_status_update': // Backend sent queue status
                        // This is primarily handled by WebSocketManager, but if EventListeners
                        // needs to react to it, it can do so. (e.g., update a specific UI element)
                        break;
                    case 'status': // Generic status messages (from backend)
                        if (message.data.status === 'simulation_initiated') {
                            console.log('MessageProcessor: Simulation initiated (backend status):', message.data);
                            document.getElementById('simulationStatus').textContent = 'Running';
                            updateSystemLog(`Simulation: ${message.data.message || 'Started'}`);
                            if (startSimButton) {
                                startSimButton.disabled = true; // Disable start, enable stop
                                startSimButton.textContent = 'Running';
                            }
                            if (stopSimButton) stopSimButton.disabled = false;
                        } else if (message.data.status === 'simulation_stopped') {
                            console.log('MessageProcessor: Simulation stopped (backend status):', message.data);
                            document.getElementById('simulationStatus').textContent = 'Stopped';
                            updateSystemLog(`Simulation: ${message.data.message || 'Stopped'}`);
                            if (startSimButton) {
                                startSimButton.disabled = false; // Enable start, disable stop
                                startSimButton.textContent = 'Start Simulation';
                            }
                            if (stopSimButton) stopSimButton.disabled = true;
                        } else {
                            console.log('MessageProcessor: Generic status message:', message.data);
                            updateStatusLog(`Status: ${JSON.stringify(message.data)}`);
                        }
                        break;
                    case 'frontend_ready_ack':
                        console.log('MessageProcessor: Backend acknowledged frontend readiness.');
                        updateSystemLog(`Backend: Frontend ready acknowledged.`);
                        break;
                    case 'transcription_result':
                        console.log('MessageProcessor: Transcription result received:', message.data);
                        updateTranscriptionLog(message.data.text || JSON.stringify(message.data));
                        frontendDisplayQueue.enqueue(message); // Enqueue for display if needed
                        break;
                    case 'data': // Generic data message (e.g., translation results)
                        console.log('MessageProcessor: Data/result received:', message.data);
                        // Assuming this is for translation output
                        document.getElementById('translationOutput').textContent = message.data.translated_text || JSON.stringify(message.data, null, 2);
                        const translationLoading = document.getElementById('translationLoading');
                        if (translationLoading) {
                            translationLoading.classList.add('hidden');
                        }
                        if (translateButton) translateButton.disabled = false; // Re-enable translate button
                        frontendDisplayQueue.enqueue(message);
                        break;
                    case 'settings_updated_ack': // Acknowledge from backend for settings update
                        updateStatusLog(`Backend confirmed settings update: ${JSON.stringify(message.data)}`);
                        console.log('Backend confirmed settings update:', message.data);
                        break;
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type, message);
                        updateSystemLog(`Unknown message type: ${message.type} - ${JSON.stringify(message.data || {}).substring(0,100)}...`);
                }
            } catch (processError) {
                console.error('MessageProcessor: Error processing message:', processError, message);
                updateSystemLog(`Error processing message: ${processError.message}. Message: ${JSON.stringify(message || {}).substring(0,100)}...`);
            }
            updateAllQueueDisplays(); // Always refresh display after processing a message
        }
    } catch (error) {
        console.error('MessageProcessor: Fatal error in message processing loop:', error);
        updateSystemLog(`Fatal error in message processor: ${error.message}`);
    } finally {
        console.groupEnd();
        processBackendMessages._running = false;
        console.log('MessageProcessor: Message processing loop stopped.');
        updateSystemLog('Message processing loop stopped.');
    }
}

// Ensure the loop can be stopped if needed (e.g., on app shutdown)
export function stopProcessingBackendMessages() {
    processBackendMessages._running = false;
    console.log('MessageProcessor: Stop requested. Loop will terminate soon.');
}