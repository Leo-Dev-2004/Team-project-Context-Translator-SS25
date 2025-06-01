// frontend/src/modules/EventListeners.js

import { WebSocketManager } from './WebSocketManager.js'; // Imports the singleton instance
import {
    updateSystemLog,
    updateStatusLog,
    updateTestLog,
    updateAllQueueDisplays,
    updateSimulationLog // Ensure this is imported for transcription results
} from './QueueDisplay.js';

let toBackendQueue;
let fromBackendQueue; // This is the crucial queue for incoming messages
let frontendDisplayQueue;
let frontendActionQueue;

let webSocketManagerInstance; // This will hold the singleton instance passed from app.js

let isWebSocketReady = false; // Initial state: not ready

let startSimButton;
let stopSimButton;
let sendTestMessageButton;
let sendTranscriptionButton;


export function setQueuesAndManager(queues, manager) {
    toBackendQueue = queues.toBackendQueue;
    fromBackendQueue = queues.fromBackendQueue;
    frontendDisplayQueue = queues.frontendDisplayQueue;
    frontendActionQueue = queues.frontendActionQueue;
    webSocketManagerInstance = manager;
    console.log('EventListeners: Queues and WebSocketManager assigned.');
}

function disableActionButtons() {
    console.log('EventListeners: Disabling action buttons.');
    if (startSimButton) startSimButton.disabled = true;
    if (stopSimButton) stopSimButton.disabled = true;
    if (sendTestMessageButton) sendTestMessageButton.disabled = true;
    if (sendTranscriptionButton) sendTranscriptionButton.disabled = true;
    updateSystemLog('Action buttons disabled (waiting for WebSocket connection).');
}

function enableActionButtons() {
    console.log('EventListeners: Enabling action buttons.');
    if (startSimButton) startSimButton.disabled = false;
    if (stopSimButton) stopSimButton.disabled = false;
    if (sendTestMessageButton) sendTestMessageButton.disabled = false;
    if (sendTranscriptionButton) sendTranscriptionButton.disabled = false;
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
        console.log('EventListeners: WebSocket fully initialized and acknowledged by server. Starting message processor.');
        // Ensure processBackendMessages is called only once after connection is ready
        if (!processBackendMessages._started) {
            processBackendMessages._started = true; // Set flag before starting
            // The processBackendMessages loop is now initiated by app.js,
            // but this state change ensures it *acts* on messages.
            processBackendMessages(); // Re-call in case it stopped due to isWebSocketReady being false
        }

    } else {
        disableActionButtons();
        console.log('EventListeners: WebSocket not ready. Disabling message processor.');
        // If needed, add logic here to explicitly stop the message processing loop
        // For now, the while(isWebSocketReady) condition handles pausing.
    }
}


export function initializeEventListeners() {
    console.log('EventListeners: Initializing...');

    // Assign button references FIRST
    startSimButton = document.getElementById('startSim');
    stopSimButton = document.getElementById('stopSim');
    sendTestMessageButton = document.getElementById('sendTestMessage'); // Corrected ID
    sendTranscriptionButton = document.getElementById('sendTranscription');

    // Initially disable all action buttons (this ensures they are disabled immediately on page load)
    disableActionButtons();

    // Add event listeners (these will only send messages if isWebSocketReady is true)
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
                
                // Disable button until response received
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
                updateSystemLog('User clicked: Stop Simulation');
                webSocketManagerInstance.sendMessage({
                    type: 'command',
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

    console.log('EventListeners: Buttons assigned.');
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
        id: 123454321
    };
    console.log("DEBUG: Prepared test message:", testMessage);
    webSocketManagerInstance.sendMessage(testMessage);
    console.log("DEBUG: sendTestMessage completed, message passed to WebSocketManager.");

    updateSystemLog('Sent Test Message to Backend');
}

export async function processBackendMessages() {
    if (processBackendMessages._running) {
        console.warn('MessageProcessor: Loop already running.');
        return;
    }
    processBackendMessages._running = true;
    console.group('MessageProcessor: Starting message processing loop...');

    try {
        while (processBackendMessages._running) { // Loop until explicitly stopped or `isWebSocketReady` is false
            // Only dequeue if WebSocket is ready. Otherwise, pause dequeuing.
            if (!isWebSocketReady) {
                // If not ready, wait a bit and check again without dequeuing
                await new Promise(resolve => setTimeout(resolve, 500)); // Longer wait if not ready
                continue;
            }

            const message = await fromBackendQueue.dequeue();

            if (!message) {
                // If queue is empty, wait briefly before checking again
                await new Promise(resolve => setTimeout(resolve, 50));
                continue;
            }

            console.log('MessageProcessor: Dequeued message from backend:', message);
            await new Promise(resolve => setTimeout(resolve, 10)); // Simulate processing delay

            try {
                // Instead of processing messages here, delegate to the observer.
                // The observer is set up in app.js and passed to WebSocketManager.
                // WebSocketManager now calls the observer's handleMessage directly on receipt.
                // This 'processBackendMessages' loop primarily ensures that messages
                // are consumed from `fromBackendQueue` and then passed to the observer.
                // If you want the observer to be called *after* dequeuing here,
                // you would need to pass the observer instance to this module too,
                // or have `WebSocketManager` enqueue messages to `fromBackendQueue`
                // and *then* the observer polls from `fromBackendQueue`.

                // For the current design, `WebSocketManager` handles calling the observer immediately.
                // So, this loop mainly ensures the queue itself doesn't overflow.
                // The `switch` statement logic should ideally move to `SimulationObserver`'s `handleMessage`.

                // For demonstration, let's keep the core processing logic here if you want EventListeners
                // to explicitly dequeue and process. However, if `WebSocketManager` calls the observer,
                // then this `switch` block is redundant and `fromBackendQueue` might not be needed for direct processing by EventListeners.
                // Let's assume `fromBackendQueue` is for this EventListeners' processing loop.
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected (Acknowledged)';
                        setWebSocketReadyState(true); // <--- Call it here to enable buttons!
                        updateSystemLog(`Connection acknowledged by backend. Client ID: ${message.data.client_id}`);
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
                    case 'status_update':
                        console.log('MessageProcessor: Status update received:', message.data);
                        const statusLogMessage = `Status: ${message.data.original_type || 'unknown'} processed (ID: ${message.data.id || message.data.original_id || 'N/A'})`;
                        updateStatusLog(statusLogMessage);
                        break;
                    case 'test_message':
                        console.log('MessageProcessor: Test message received (backend response):', message.data);
                        updateTestLog(`Test Message Response: ${message.data.content || message.data.text || JSON.stringify(message.data)}`);
                        break;
                    case 'simulation_status_update':
                        console.log('MessageProcessor: Simulation status update received (old type):', message.data);
                        updateSimulationLog(message.data);
                        break;
                    case 'agent_log':
                        console.log('MessageProcessor: Agent log received:', message.data);
                        updateSystemLog(`Agent Log: ${JSON.stringify(message.data)}`);
                        break;
                    case 'queue_counters':
                        console.log('MessageProcessor: Queue counters received:', message.data);
                        // The HTML script handles this via window.appQueues, but you could process
                        // specific backend-sent counters here if needed.
                        break;
                    case 'status':
                        if (message.data.status === 'simulation_initiated') {
                            console.log('MessageProcessor: Simulation initiated (backend status):', message.data);
                            document.getElementById('simulationStatus').textContent = 'Running';
                            updateSystemLog(`Simulation: ${message.data.message || 'Started'}`);
                        } else if (message.data.status === 'simulation_stopped') {
                            console.log('MessageProcessor: Simulation stopped (backend status):', message.data);
                            document.getElementById('simulationStatus').textContent = 'Stopped';
                            updateSystemLog(`Simulation: ${message.data.message || 'Stopped'}`);
                        } else {
                            console.log('MessageProcessor: Generic status message:', message.data);
                            updateSystemLog(`Status: ${JSON.stringify(message.data)}`);
                        }
                        break;
                    case 'frontend_ready_ack':
                        console.log('MessageProcessor: Backend acknowledged frontend readiness.');
                        updateSystemLog(`Backend: Frontend ready acknowledged.`);
                        break;
                    case 'transcription_result':
                        console.log('MessageProcessor: Transcription result received:', message.data);
                        // Enqueue to frontendDisplayQueue if it's meant for displaying general messages
                        // or call a specific update function like updateTranscriptionLog
                        updateTranscriptionLog(message.data); // Assuming this exists in QueueDisplay.js
                        frontendDisplayQueue.enqueue(message); // Keep if you want it in the display queue
                        break;
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type, message);
                        updateSystemLog(`Unknown message type: ${message.type} - ${JSON.stringify(message.data).substring(0,100)}...`);
                }
            } catch (processError) {
                console.error('MessageProcessor: Error processing message:', processError, message);
                updateSystemLog(`Error processing message: ${processError.message}. Message: ${JSON.stringify(message).substring(0,100)}...`);
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
