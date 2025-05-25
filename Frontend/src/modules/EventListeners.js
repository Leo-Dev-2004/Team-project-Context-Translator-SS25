// frontend/src/modules/EventListeners.js
import { fromFrontendQueue, fromBackendQueue, toFrontendQueue, toBackendQueue } from '../app.js';
import { startSimulation, stopSimulation } from './SimulationManager.js'; // Import specific functions
import { updateAllQueueDisplays, updateQueueLog, updateQueueCounters, updateQueueDisplay } from './QueueDisplay.js'; // Import specific functions
import { WebSocketManager } from './WebSocketManager.js'; // Import the WebSocketManager object


// Function for the Test Message button
function sendTestMessage() {
    console.log("TRACE: sendTestMessage called!");
    const testMessage = {
        type: 'test_message',
        data: {
            text: 'Hello from Frontend Test Button!',
            timestamp: new Date().toISOString(),
            id: 'test_msg_' + Date.now() // Add an ID, as your backend validator was looking for it
        }
    };
    fromFrontendQueue.enqueue(testMessage); // Enqueue for potential internal processing/logging
    console.log("DEBUG: Test message enqueued to fromFrontendQueue. Current size:", fromFrontendQueue.size());

    // --- ADD THIS LINE TO IMMEDIATELY SEND IT ---
    WebSocketManager.sendMessage(testMessage);
    console.log("DEBUG: Test message enqueued to fromFrontendQueue. Current size:", fromFrontendQueue.size());
    updateQueueDisplay('fromFrontendQueue', fromFrontendQueue, 'fromFrontendQueueDisplay'); // ENSURE THIS IS PRESENT
}


// This function will continuously process messages from the fromBackendQueue
export async function processBackendMessages() {
    console.group('MessageProcessor: Starting message processing loop...');
    try {
        while (true) {
            // Wait for a message to be available in the queue
            const message = await fromBackendQueue.dequeue();
            if (!message) {
                console.warn('MessageProcessor: Received empty message, skipping');
                continue;
            }

            console.log('MessageProcessor: Dequeued message from backend:', message);

            // Process the message based on its type
            try {
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend connection acknowledged:', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected (Acknowledged)';
                        updateQueueLog('system_log', `System: Connection acknowledged by backend`);
                        break;
                    case 'system':
                        console.log('MessageProcessor: System message received:', message.data);
                        document.getElementById('simulationStatus').textContent = message.data.message;
                        updateSystemLog(message.data);
                        updateQueueLog('system_log', `System: ${message.data.message}`);
                        break;
                    case 'simulation_update':
                        console.log('MessageProcessor: Simulation update received:', message.data);
                        updateQueueLog('simulation_log', 
                            `Sim Update: ID=${message.data.id}, Status=${message.data.status}`);
                        break;
                    case 'status_update':
                        console.log('MessageProcessor: Status update received:', message.data);
                        // Korrekte Aufrufweise mit Queue als zweitem Parameter
                        const logMessage = `Status: ${message.data.original_type} processed`;
                        document.getElementById('status_log').textContent += logMessage + '\n';
                        break;
                    case 'test_message':
                        console.log('MessageProcessor: Test message received:', message.data);
                        showTestMessageResponse(message.data);
                        updateQueueLog('test_log', 
                            `Test Message: ${message.data.content}`);
                        break;
                    case 'simulation_status_update':
                        console.log('MessageProcessor: Simulation status update received:', message.data);
                        updateQueueDisplay(message.data);
                        break;
                    case 'agent_log':
                        console.log('MessageProcessor: Agent log received:', message.data);
                        updateQueueLog('agent_log', message.data);
                        break;
                    case 'queue_counters':
                        console.log('MessageProcessor: Queue counters received:', message.data);
                        updateQueueCounters(message.data);
                        break;
                    case 'simulation_started':
                        console.log('MessageProcessor: Simulation started:', message.data);
                        document.getElementById('simulationStatus').textContent = 'Running';
                        break;
                    case 'simulation_stopped':
                        console.log('MessageProcessor: Simulation stopped:', message.data);
                        document.getElementById('simulationStatus').textContent = 'Stopped';
                        break;
                    case 'frontend_ready_ack':
                        console.log('MessageProcessor: Backend acknowledged frontend readiness.');
                        break;
                    default:
                        console.warn('MessageProcessor: Unknown message type:', message.type);
                        handleUnknownMessage(message);
                }
            } catch (processError) {
                console.error('MessageProcessor: Error processing message:', processError, message);
                handleProcessingError(processError, message);
            }
        }
    } catch (error) {
        console.error('MessageProcessor: Fatal error in message processing loop:', error);
        showFatalError(error);
    } finally {
        console.groupEnd();
    }
}

// Helper functions
function showErrorNotification(error) {
    const errorElement = document.getElementById('errorDisplay');
    if (errorElement) {
        errorElement.textContent = `Error: ${error}`;
        errorElement.style.display = 'block';
        setTimeout(() => errorElement.style.display = 'none', 5000);
    }
}

function updateSystemLog(data) {
    const logElement = document.getElementById('systemLog');
    if (logElement) {
        logElement.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${data.message}</div>`;
    }
}

function showTestMessageResponse(data) {
    const testResponseElement = document.getElementById('testResponse');
    if (testResponseElement) {
        testResponseElement.textContent = `Test response: ${data.text}`;
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
        errorLog.innerHTML += `<div>Error processing ${message.type}: ${error.message}</div>`;
    }
}

function showFatalError(error) {
    const fatalErrorElement = document.getElementById('fatalError');
    if (fatalErrorElement) {
        fatalErrorElement.textContent = `Fatal error: ${error.message}. Please reload the page.`;
        fatalErrorElement.style.display = 'block';
    }
}


// Event listener setup
export function initializeEventListeners() {
    console.group('EventListeners: Initializing...');

    // Assign event handlers to buttons
    document.getElementById('startSim').addEventListener('click', () => {
        startSimulation();
        console.log('EventListeners: startSim button clicked.');
    });
    document.getElementById('stopSim').addEventListener('click', () => {
        stopSimulation();
        console.log('EventListeners: stopSim button clicked.');
    });
    document.getElementById('testButton').addEventListener('click', sendTestMessage);
    console.log('EventListeners: Buttons assigned.');

    // Listen for WebSocket connection acknowledgement
    document.addEventListener('websocket-ack', () => {
        console.log('EventListeners: WebSocket fully initialized and acknowledged by server. Starting message processor.');
        // Once WebSocket is confirmed, start processing messages from the backend
        processBackendMessages();
        // You might want an initial display update here too
        updateQueueDisplay({ /* initial empty state or current state */ });
        updateQueueCounters({ /* initial empty state */ });
    });

    console.log('EventListeners: Initialization complete.');
    console.groupEnd();
}
