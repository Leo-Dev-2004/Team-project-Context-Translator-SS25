// frontend/src/modules/EventListeners.js
import { fromFrontendQueue, fromBackendQueue, toFrontendQueue, toBackendQueue } from '../app.js';
import { startSimulation, stopSimulation } from './SimulationManager.js'; // Import specific functions
import { updateQueueDisplay, updateQueueLog, updateQueueCounters } from './QueueDisplay.js'; // Import specific functions
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
    // --- END ADDITION ---
}


// This function will continuously process messages from the fromBackendQueue
async function processBackendMessages() {
    console.group('Starting backend message processor');
    
    while (true) {
        try {
            const message = await fromBackendQueue.dequeue();
            console.log('Processing message:', message.type);
            
            // Update UI based on message type
            switch(message.type) {
                case 'system':
                    document.getElementById('simulationStatus').textContent = 
                        message.data.message || 'System update';
                    break;
                case 'simulation_update':
                    document.getElementById('simulationProgress').textContent = 
                        `Progress: ${message.data.progress}%`;
                    break;
                default:
                    console.warn('Unhandled message type:', message.type);
            }
            
            // Update all queue displays
            updateQueueDisplay(message);
            
            console.log('MessageProcessor: Dequeued message from backend:', message);

            // Process the message based on its type
            switch (message.type) {
                case 'simulation_status_update':
                    console.log('MessageProcessor: Simulation status update received:', message.payload);
                    updateQueueDisplay(message.data);
                    break;
                case 'agent_log':
                    console.log('MessageProcessor: Agent log received:', message.payload);
                    updateQueueLog(message.data);
                    break;
                case 'queue_counters':
                    console.log('MessageProcessor: Queue counters received:', message.payload);
                    updateQueueCounters(message.data);
                    break;
                case 'connection_ack':
                    console.log('MessageProcessor: Backend acknowledged connection.', message.payload);
                    break;
                case 'error':
                    console.error('MessageProcessor: Error from backend:', message.message || message.payload);
                    break;
                case 'system':
                    console.log('MessageProcessor: System message received:', message.data);
                    document.getElementById('simulationStatus').textContent = `Simulation Status: ${message.data.message}`;
                    break;
                case 'frontend_ready_ack':
                    console.log('MessageProcessor: Backend acknowledged frontend readiness.');
                    break;
                case 'message_from_backend':
                    console.log('MessageProcessor: Generic message from backend:', message.payload);
                    break;
                default:
                    console.warn('MessageProcessor: Unknown message type received:', message.type, message);
            }
        } catch (error) {
            console.error('Error processing backend message:', error);
        }
    }
    console.groupEnd();
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
