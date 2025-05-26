// frontend/src/modules/EventListeners.js
// IMPORTANT: Ensure these imports are correct and complete.
import {
    fromFrontendQueue,
    fromBackendQueue,
    toFrontendQueue,
    toBackendQueue
} from '../app.js';

import { startSimulation, stopSimulation } from './SimulationManager.js';

// Import ALL necessary display and log functions from QueueDisplay.js
import {
    updateAllQueueDisplays,
    updateQueueDisplay,
    updateQueueCounters,
    updateSystemLog,      // Now correctly imported
    updateSimulationLog,  // Now correctly imported
    updateStatusLog,      // Now correctly imported
    updateTestLog         // Now correctly imported
} from './QueueDisplay.js';

import { WebSocketManager } from './WebSocketManager.js';


// Function for the Test Message button
function sendTestMessage() {
    console.log("TRACE: sendTestMessage called!");
    const testMessage = {
        type: 'test_message',
        data: {
            text: 'Hello from Frontend Test Button!',
            timestamp: Date.now() / 1000,
            id: 'test_msg_' + Date.now(),
            status: 'pending_frontend'
        }
    };

    // Enqueue and update display immediately
    frontendActionQueue.enqueue(testMessage);
    // Correct call: (QUEUE_OBJECT, 'ELEMENT_ID_STRING')
    updateQueueDisplay(frontendActionQueue, 'fromFrontendQueueDisplay');

    // Send via WebSocket
    WebSocketManager.sendMessage(testMessage);
    console.log("DEBUG: Test message sent to backend");
    updateTestLog(`Sent test message: ${testMessage.data.text}`); // Log the sending
}


// This function will continuously process messages from the fromBackendQueue
export async function processBackendMessages() {
    console.group('MessageProcessor: Starting message processing loop...');
    try {
        while (true) {
            // Wait for a message to be available in the queue
            const message = await fromBackendQueue.dequeue();
            if (!message) {
                // console.warn('MessageProcessor: Received empty message, skipping'); // Removed for less console noise
                await new Promise(resolve => setTimeout(resolve, 50)); // Small delay to prevent busy-waiting
                continue;
            }

            console.log('MessageProcessor: Dequeued message from backend:', message);

            // Process the message based on its type
            try {
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected (Acknowledged)';
                        updateSystemLog(`Connection acknowledged by backend`); // Use imported function
                        break;
                    case 'system':
                        console.log('MessageProcessor: System message received:', message.data);
                        document.getElementById('simulationStatus').textContent = message.data.message;
                        updateSystemLog(message.data); // Use imported function
                        break;
                    case 'simulation_update':
                        console.log('MessageProcessor: Simulation update received:', message.data);
                        updateSimulationLog(message.data); // Use imported function
                        break;
                    case 'status_update':
                        console.log('MessageProcessor: Status update received:', message.data);
                        const statusLogMessage = `Status: ${message.data.original_type || 'unknown'} processed (ID: ${message.data.id || message.data.original_id || 'N/A'})`;
                        updateStatusLog(statusLogMessage); // Use imported function
                        break;
                    case 'test_message':
                        console.log('MessageProcessor: Test message received:', message.data);
                        showTestMessageResponse(message.data); // Still using local helper for specific UI
                        updateTestLog(`Test Message: ${message.data.content || message.data.text}`); // Use imported function
                        break;
                    case 'simulation_status_update': // This type seems unused or misnamed from backend, treating as sim log
                        console.log('MessageProcessor: Simulation status update received (old type):', message.data);
                        updateSimulationLog(message.data); // Use imported function
                        break;
                    case 'agent_log': // If this type is used, uncomment and implement properly
                        console.log('MessageProcessor: Agent log received:', message.data);
                        // Assuming you have an 'agent_log' div and a proper updateAgentLog function imported/defined
                        // For now, if not implemented, it will just log to console.
                        updateSystemLog(`Agent Log: ${JSON.stringify(message.data)}`); // Placeholder if no dedicated agent log
                        break;
                    case 'queue_counters': // If backend sends this, update the display via updateAllQueueDisplays
                        console.log('MessageProcessor: Queue counters received:', message.data);
                        // updateQueueCounters() is called by updateAllQueueDisplays, no direct call needed here
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
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type, message);
                        handleUnknownMessage(message);
                }
            } catch (processError) {
                console.error('MessageProcessor: Error processing message:', processError, message);
                handleProcessingError(processError, message);
            }
            // CRITICAL: Update all queue displays after each message is processed from backend
            updateAllQueueDisplays();
        }
    } catch (error) {
        console.error('MessageProcessor: Fatal error in message processing loop:', error);
        showFatalError(error);
    } finally {
        console.groupEnd();
    }
}

// Helper functions (these are local to EventListeners.js for specific UI elements)
function showErrorNotification(error) {
    const errorElement = document.getElementById('errorDisplay');
    if (errorElement) {
        errorElement.textContent = `Error: ${error}`;
        errorElement.style.display = 'block';
        setTimeout(() => errorElement.style.display = 'none', 5000);
    }
}

// NOTE: Removed conflicting local updateSystemLog function.
// It should be imported from QueueDisplay.js now.

function showTestMessageResponse(data) {
    const testResponseElement = document.getElementById('testResponse');
    if (testResponseElement) {
        testResponseElement.textContent = `Test response: ${data.text || JSON.stringify(data)}`;
    }
}

function handleUnknownMessage(message) {
    const unknownMsgElement = document.getElementById('unknownMessages');
    if (unknownMsgElement) {
        unknownMsgElement.innerHTML += `<div>Unknown type ${message.type}: ${JSON.stringify(message)}</div>`;
    }
}

function handleProcessingError(error, message) {
    console.error('Failed to process message:', error);
    const errorLog = document.getElementById('errorLog');
    if (errorLog) {
        errorLog.innerHTML += `<div>Error processing ${message.type}: ${error.message || error}</div>`;
    }
}

function showFatalError(error) {
    const fatalErrorElement = document.getElementById('fatalError');
    if (fatalErrorElement) {
        fatalErrorElement.textContent = `Fatal error: ${error.message || error}. Please reload the page.`;
        fatalErrorElement.style.display = 'block';
    }
}


// Event listener setup
export function initializeEventListeners() {
    console.group('EventListeners: Initializing...');

    // Assign event handlers to buttons
    document.getElementById('startSim').addEventListener('click', () => {
        // Enqueue a 'start_simulation' command to fromFrontendQueue
        const startCommand = {
            type: 'command',
            data: {
                command: 'start_simulation',
                timestamp: new Date().toISOString(),
                id: 'cmd_start_' + Date.now(),
                status: 'pending_frontend'
            }
        };
        frontendActionQueue.enqueue(startCommand);
        updateQueueDisplay(frontendActionQueue, 'fromFrontendQueueDisplay'); // Update its display
        WebSocketManager.sendMessage(startCommand); // Send to backend
        console.log('EventListeners: startSim button clicked, command sent.');
    });

    document.getElementById('stopSim').addEventListener('click', () => {
        // Enqueue a 'stop_simulation' command to fromFrontendQueue
        const stopCommand = {
            type: 'command',
            data: {
                command: 'stop_simulation',
                timestamp: new Date().toISOString(),
                id: 'cmd_stop_' + Date.now(),
                status: 'pending_frontend'
            }
        };
        frontendActionQueue.enqueue(stopCommand);
        updateQueueDisplay(frontendActionQueue, 'fromFrontendQueueDisplay'); // Update its display
        WebSocketManager.sendMessage(stopCommand); // Send to backend
        console.log('EventListeners: stopSim button clicked, command sent.');
    });

    document.getElementById('testButton').addEventListener('click', sendTestMessage);
    console.log('EventListeners: Buttons assigned.');

    // Listen for WebSocket connection acknowledgement
    document.addEventListener('websocket-ack', () => {
        console.log('EventListeners: WebSocket fully initialized and acknowledged by server. Starting message processor.');
        // Once WebSocket is confirmed, start processing messages from the backend
        processBackendMessages(); // This will start the continuous loop
        // Initial display update for all queues when connection is established
        updateAllQueueDisplays(); // One initial update
    });

    // Set up a continuous loop to update all queue displays for dynamic changes
    // This will run even if no messages are processed by processBackendMessages (e.g., initially or during idle periods)
    setInterval(updateAllQueueDisplays, 500); // Update every 500ms

    console.log('EventListeners: Initialization complete.');
    console.groupEnd();
}
