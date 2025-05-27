// frontend/src/modules/EventListeners.js

import { WebSocketManager } from './WebSocketManager.js'; // Ensure correct import
import {
    updateSystemLog,
    updateStatusLog,
    updateTestLog,
    updateAllQueueDisplays,
    updateSimulationLog
} from './QueueDisplay.js'; // Re-import updated QueueDisplay functions

// Existing references to queues from app.js (will now be set via a function)
let toBackendQueue;
let fromBackendQueue;
let frontendDisplayQueue; // For messages that need to pop up or be dynamically displayed
let frontendActionQueue; // For messages that represent user actions/inputs

let webSocketManagerInstance; // Reference to the WebSocketManager instance

// Set up the queues and WebSocketManager instance
export function setQueuesAndManager(queues, manager) {
    toBackendQueue = queues.toBackendQueue;
    fromBackendQueue = queues.fromBackendQueue;
    frontendDisplayQueue = queues.frontendDisplayQueue;
    frontendActionQueue = queues.frontendActionQueue;
    webSocketManagerInstance = manager; // Assign the manager instance
    console.log('EventListeners: Queues and WebSocketManager assigned.');

    // This is crucial: Make sure the QueueDisplay module also gets the queue references.
    // If QueueDisplay relies on its own setQueues, call that here.
    // (This was already added in WebSocketManager, so just ensure it's propagated correctly)
}


// --- Frontend Event Listeners ---
export function initializeEventListeners() {
    console.log('EventListeners: Initializing...');

    // Assign button click handlers
    const startSimButton = document.getElementById('startSim');
    if (startSimButton) {
        startSimButton.addEventListener('click', () => {
            console.log('EventListeners: startSim button clicked, command sent.');
            updateSystemLog('User clicked: Start Simulation');
            webSocketManagerInstance.sendMessage({ // Use the manager instance
                type: 'command',
                data: {
                    command: 'start_simulation'
                },
                timestamp: Date.now()
            });
        });
    }

    const stopSimButton = document.getElementById('stopSim');
    if (stopSimButton) {
        stopSimButton.addEventListener('click', () => {
            console.log('EventListeners: stopSim button clicked, command sent.');
            updateSystemLog('User clicked: Stop Simulation');
            webSocketManagerInstance.sendMessage({ // Use the manager instance
                type: 'command',
                data: {
                    command: 'stop_simulation'
                },
                timestamp: Date.now()
            });
        });
    }

    const sendTestMessageButton = document.getElementById('sendTestMessage');
    if (sendTestMessageButton) {
        sendTestMessageButton.addEventListener('click', () => {
            sendTestMessage();
        });
    }

    // Assign other event listeners as needed, e.g., for transcription
    const sendTranscriptionButton = document.getElementById('sendTranscription');
    if (sendTranscriptionButton) {
        sendTranscriptionButton.addEventListener('click', () => {
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
                transcriptionInput.value = ''; // Clear input after sending
            } else {
                updateSystemLog("Transcription input is empty.");
            }
        });
    }

    // Set up queue display update interval for visibility
    // setInterval(updateAllQueueDisplays, 1000); // Already handled by requestAnimationFrame in updateAllQueueDisplays

    console.log('EventListeners: Buttons assigned.');

    // Listen for the custom event when WebSocket is acknowledged by the server
    document.addEventListener('websocket-ack', () => {
        console.log('EventListeners: WebSocket fully initialized and acknowledged by server. Starting message processor.');
        // Only start the processor once WebSocket is ready
        processBackendMessages();
    });

    console.log('EventListeners: Initialization complete.');
}

// Function to send a test message
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
    console.log("DEBUG: Prepared test message:", testMessage); // <--- ADD THIS
    webSocketManagerInstance.sendMessage(testMessage); // Use the manager instance
    console.log("DEBUG: sendTestMessage completed, message passed to WebSocketManager."); // <--- ADD THIS
    
    updateSystemLog('Sent Test Message to Backend');
}

// Function to handle backend messages (this will run in a continuous loop)
export async function processBackendMessages() {
    console.group('MessageProcessor: Starting message processing loop...');
    try {
        while (true) {
            // Wait for a message to be available in the queue.
            // This is a blocking call (asynchronous, but waits for item).
            const message = await fromBackendQueue.dequeue(); // This truly removes the item

            console.log('MessageProcessor: Dequeued message from backend:', message);

            // --- SIMULATE PROCESSING DELAY HERE ---
            await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate 1 second of processing

            // Process the message based on its type
            try {
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected (Acknowledged)';
                        updateSystemLog(`Connection acknowledged by backend`);
                        break;
                    case 'system':
                        console.log('MessageProcessor: System message received:', message.data);
                        // Update the simulation status display on the UI
                        document.getElementById('simulationStatus').textContent = message.data.message;
                        updateSystemLog(message.data);
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
                    case 'test_message': // This handles the *response* test message from backend
                        console.log('MessageProcessor: Test message received (backend response):', message.data);
                        // Assuming showTestMessageResponse and updateTestLog are defined
                        // showTestMessageResponse(message.data);
                        updateTestLog(`Test Message Response: ${message.data.content || message.data.text || JSON.stringify(message.data)}`);
                        break;
                    case 'simulation_status_update': // Old type, consider deprecating or consolidating
                        console.log('MessageProcessor: Simulation status update received (old type):', message.data);
                        updateSimulationLog(message.data);
                        break;
                    case 'agent_log':
                        console.log('MessageProcessor: Agent log received:', message.data);
                        updateSystemLog(`Agent Log: ${JSON.stringify(message.data)}`);
                        break;
                    case 'queue_counters': // Backend sends queue stats
                        console.log('MessageProcessor: Queue counters received:', message.data);
                        // No direct UI update needed here, as updateAllQueueDisplays handles UI queues
                        break;
                    case 'simulation_started':
                        console.log('MessageProcessor: Simulation started (backend event):', message.data);
                        document.getElementById('simulationStatus').textContent = 'Running';
                        updateSystemLog(`Simulation: ${message.data.message || 'Started'}`);
                        break;
                    case 'simulation_stopped':
                        console.log('MessageProcessor: Simulation stopped (backend event):', message.data);
                        document.getElementById('simulationStatus').textContent = 'Stopped';
                        updateSystemLog(`Simulation: ${message.data.message || 'Stopped'}`);
                        break;
                    case 'frontend_ready_ack':
                        console.log('MessageProcessor: Backend acknowledged frontend readiness.');
                        updateSystemLog(`Backend: Frontend ready acknowledged.`);
                        break;
                    case 'transcription_result': // Example: Backend sends transcription
                        console.log('MessageProcessor: Transcription result received:', message.data);
                        // Enqueue to a queue specific for popup displays if needed
                        frontendDisplayQueue.enqueue(message);
                        // Add logic here to trigger your popup update based on frontendDisplayQueue
                        break;
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type, message);
                        // handleUnknownMessage(message); // If you have a generic handler
                }
            } catch (processError) {
                console.error('MessageProcessor: Error processing message:', processError, message);
                // handleProcessingError(processError, message); // If you have a generic handler
            }
            // CRITICAL: Update all queue displays after each message is processed from backend
            updateAllQueueDisplays();
        }
    } catch (error) {
        console.error('MessageProcessor: Fatal error in message processing loop:', error);
        // showFatalError(error); // If you have a generic error display
    } finally {
        console.groupEnd();
    }
}

// Placeholder for `showTestMessageResponse` if not defined elsewhere
function showTestMessageResponse(data) {
    console.log("Test message response received:", data);
    // Example: update a specific element on your page
    const responseElement = document.getElementById('testMessageResponse');
    if (responseElement) {
        responseElement.textContent = `Response: ${data.text || JSON.stringify(data)}`;
    }
}