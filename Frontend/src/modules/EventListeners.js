// Frontend/src/modules/EventListeners.js

import { updateSystemLog, updateStatusLog, updateSimulationLog, updateTestLog, updateTranscriptionLog } from './QueueDisplay.js';
import { WebSocketManager } from './WebSocketManager.js'; // Still needed for isConnected/isWebSocketReady
import { MessageQueue } from './MessageQueue.js'; // Only if you create new queues here, otherwise remove
import { MessagingService } from './MessagingService.js'; // Import the new service

let fromBackendQueue; // The main incoming queue from backend
let frontendDisplayQueue; // Internal queue for messages that need to be processed for UI display
let webSocketManager; // Reference to WebSocketManager to check isConnected/isWebSocketReady state
let translateButton; // Assuming this is defined globally or passed somehow
let startSimButton;
let stopSimButton;

let isWebSocketReady = false; // Internal state to control message processing

const setWebSocketReadyState = (state) => {
    isWebSocketReady = state;
    // Potentially enable/disable buttons based on connection state here
    if (translateButton) translateButton.disabled = !state;
    // ... other buttons
};

const setupEventListeners = (dependencies) => {
    webSocketManager = dependencies.webSocketManager; // Still needed for isConnected
    // Get queues from the MessagingService
    fromBackendQueue = dependencies.fromBackendQueue;
    frontendDisplayQueue = dependencies.frontendDisplayQueue;

    // Direct DOM element references
    translateButton = document.getElementById('translateText');
    const sourceText = document.getElementById('sourceText');
    const clearTextButton = document.getElementById('clearText');
    const saveSettingsButton = document.getElementById('saveSettings');
    const translationMode = document.getElementById('translationMode');
    const contextLevel = document.getElementById('contextLevel');
    startSimButton = document.getElementById('startSimulation'); // Assuming you have these buttons
    stopSimButton = document.getElementById('stopSimulation');


    // Ensure buttons are initially disabled until connected
    if (translateButton) translateButton.disabled = true;
    if (startSimButton) startSimButton.disabled = true;
    if (stopSimButton) stopSimButton.disabled = true;

    // --- Message Processing for FrontendDisplayQueue ---
    // This loop now processes messages from the frontendDisplayQueue
    // which is fed by the MessagingService's observer
    processFrontendDisplayQueueMessages();

    // --- UI Event Listeners ---
    if (translateButton) {
        translateButton.addEventListener('click', () => {
            const text = sourceText.value;
            if (text.trim() === '') {
                updateSystemLog('Source text is empty. Cannot translate.');
                return;
            }
            translateButton.disabled = true; // Disable while translating
            const translationLoading = document.getElementById('translationLoading');
            if (translationLoading) translationLoading.classList.remove('hidden');

            MessagingService.sendToBackend(
                'translation_request',
                { text: text, mode: translationMode.value, context_level: parseInt(contextLevel.value) }
            );
            updateSystemLog('Translation request sent.');
        });
    }

    if (clearTextButton) {
        clearTextButton.addEventListener('click', () => {
            sourceText.value = '';
            document.getElementById('translationOutput').textContent = '';
            updateSystemLog('Text cleared.');
        });
    }

    if (saveSettingsButton) {
        saveSettingsButton.addEventListener('click', () => {
            // Using MessagingService to send settings
            MessagingService.sendToBackend(
                'update_settings',
                {
                    mode: translationMode.value,
                    context_level: parseInt(contextLevel.value)
                }
            );
            updateSystemLog('Settings update request sent.');
        });
    }

    // Example for simulation buttons (if you have them)
    if (startSimButton) {
        startSimButton.addEventListener('click', () => {
            MessagingService.sendToBackend('start_simulation', { message: 'Start simulation' });
            updateSystemLog('Start simulation request sent.');
            startSimButton.disabled = true;
            stopSimButton.disabled = false;
        });
    }

    if (stopSimButton) {
        stopSimButton.addEventListener('click', () => {
            MessagingService.sendToBackend('stop_simulation', { message: 'Stop simulation' });
            updateSystemLog('Stop simulation request sent.');
            stopSimButton.disabled = true;
            startSimButton.disabled = false;
        });
    }
};

// --- Frontend Display Queue Processor ---
// This loop processes messages specifically destined for UI display
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
            // Dequeue from the frontendDisplayQueue
            const message = await frontendDisplayQueue.dequeue(); // This queue is populated by MessagingService

            // Reduce this delay significantly or remove it entirely
            await new Promise(resolve => setTimeout(resolve, 100)); // Reduced from 2000ms

            if (message) {
                console.log('FrontendDisplayQueue Processor: Dequeued message for display:', message);

                // --- Message Type Dispatch (Moved from app.js / old WebSocketManager observer) ---
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected (Acknowledged)';
                        setWebSocketReadyState(true); // Now in EventListeners to manage UI state
                        updateSystemLog(`Connection acknowledged by backend. Client ID: ${message.data.client_id}`);
                        break;
                    case 'backend_ready_confirm':
                        updateStatusLog(`Backend Ready: ${message.payload.message}`);
                        break;
                    case 'system_info':
                        console.log('MessageProcessor: System message received:', message.payload);
                        document.getElementById('simulationStatus').textContent = message.payload.message;
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
                            const translationLoading = document.getElementById('translationLoading');
                            if (translationLoading) {
                                translationLoading.classList.add('hidden');
                            }
                        }
                        break;
                    case 'test_message_response':
                        console.log('MessageProcessor: Test message received (backend response):', message.payload);
                        updateTestLog(`Test Message Response: ${message.payload.content || message.payload.text || JSON.stringify(message.payload)}`);
                        break;
                    case 'simulation_status_update':
                        console.log('MessageProcessor: Simulation status update received:', message.payload);
                        updateSimulationLog(message.payload);
                        if (message.payload.status === 'started' && startSimButton) {
                            startSimButton.disabled = false;
                            startSimButton.textContent = 'Running';
                            stopSimButton.disabled = false;
                        } else if (message.payload.status === 'stopped' && startSimButton) {
                            startSimButton.disabled = false;
                            startSimButton.textContent = 'Start Simulation';
                            stopSimButton.disabled = true;
                        }
                        break;
                    case 'agent_log':
                        console.log('MessageProcessor: Agent log received:', message.payload);
                        updateSystemLog(`Agent Log: ${JSON.stringify(message.payload)}`);
                        break;
                    case 'queue_status_update': // This might be better handled directly by WebSocketManager to update display, or by a dedicated queue status consumer
                        // For now, if it comes here, it will be logged.
                        break;
                    case 'status':
                        if (message.payload.status === 'simulation_initiated') {
                            console.log('MessageProcessor: Simulation initiated (backend status):', message.payload);
                            document.getElementById('simulationStatus').textContent = 'Running';
                            updateSystemLog(`Simulation: ${message.payload.message || 'Started'}`);
                            if (startSimButton) {
                                startSimButton.disabled = true;
                                startSimButton.textContent = 'Running';
                            }
                            if (stopSimButton) stopSimButton.disabled = false;
                        } else if (message.payload.status === 'simulation_stopped') {
                            console.log('MessageProcessor: Simulation stopped (backend status):', message.payload);
                            document.getElementById('simulationStatus').textContent = 'Stopped';
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
                        // No need to enqueue to frontendDisplayQueue here, it's already dequeued from it
                        break;
                    case 'data':
                        console.log('MessageProcessor: Data/result received:', message.payload);
                        document.getElementById('translationOutput').textContent = message.payload.translated_text || JSON.stringify(message.payload, null, 2);
                        const translationLoading = document.getElementById('translationLoading');
                        if (translationLoading) {
                            translationLoading.classList.add('hidden');
                        }
                        if (translateButton) translateButton.disabled = false;
                        break;
                    case 'settings_updated_ack':
                        updateStatusLog(`Backend confirmed settings update: ${JSON.stringify(message.payload)}`);
                        console.log('Backend confirmed settings update:', message.payload);
                        break;
                    case 'ping': // If frontend receives a ping from backend
                        console.log('Frontend received ping from backend:', message);
                        break;
                    case 'pong': // If frontend receives a pong from backend
                        console.log('Frontend received pong from backend:', message);
                        break;
                    case 'system_heartbeat': // If frontend receives a heartbeat from backend
                         console.log('Frontend received heartbeat from backend:', message);
                         updateSystemLog('Backend Heartbeat received.');
                         break;
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type, message);
                        updateSystemLog(`Unknown message type: ${message.type} - ${JSON.stringify(message.payload || {}).substring(0,100)}...`);
                }
            }
            updateAllQueueDisplays(); // Always refresh display after processing a message
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


export { setupEventListeners, setWebSocketReadyState };