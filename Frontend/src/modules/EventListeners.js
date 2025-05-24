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
            id: 'test_msg_' + Date.now()
        }
    };
    toBackendQueue.enqueue(testMessage);
    console.log("DEBUG: Test message enqueued to toBackendQueue. Current size:", toBackendQueue.size());

    WebSocketManager.sendMessage(testMessage);

    updateQueueLog('toBackendLog', toBackendQueue);
    updateAllQueueDisplays();
}


// This function will continuously process messages from the fromBackendQueue
async function processBackendMessages() {
    console.group('Starting backend message processor');
        
    while (true) {
        try {
            const message = await fromBackendQueue.dequeue();
            console.log('Processing message:', message.type);
                
            try {
                switch (message.type) {
                    case 'connection_ack':
                        console.log('MessageProcessor: Backend acknowledged connection.', message.data);
                        document.getElementById('connectionStatus').textContent = 'Connected';
                        document.getElementById('connectionStatus').style.color = 'green';
                        break;
                    case 'error':
                        console.error('MessageProcessor: Error from backend:', message.message);
                        document.getElementById('simulationStatus').textContent = `Error: ${message.message}`;
                        document.getElementById('simulationStatus').style.color = 'red';
                        break;
                    case 'system':
                        console.log('MessageProcessor: System message received:', message.data);
                        document.getElementById('simulationStatus').textContent = `Simulation Status: ${message.data.message}`;
                        document.getElementById('simulationStatus').style.color = 'blue';
                        break;
                    case 'simulation_progress_update':
                        console.log('MessageProcessor: Simulation progress update received:', message.data);
                        document.getElementById('simulationStatus').textContent = `Sim Progress: Step ${message.data.current_step}, ${message.data.overall_progress}% - ${message.data.message}`;
                        document.getElementById('simulationStatus').style.color = 'purple';
                        break;
                    case 'backend_status_update':
                        console.log('MessageProcessor: Backend processing status update received:', message.data);
                        document.getElementById('lastUpdate').textContent = `Backend Processed: ${message.data.original_type} (ID: ${message.data.original_id})`;
                        break;
                    case 'test_message':
                        console.log('MessageProcessor: Test message received (echoed/processed):', message.data);
                        document.getElementById('lastUpdate').textContent = `Test Msg Processed: ${message.data.text}`;
                        break;
                    case 'raw_simulation_data':
                        console.log('MessageProcessor: Raw simulation data received:', message.data);
                        document.getElementById('messageCount').textContent = parseInt(document.getElementById('messageCount').textContent) + 1;
                        break;
                    case 'status_update':
                        console.log('MessageProcessor: Generic status_update received:', message.data);
                        document.getElementById('lastUpdate').textContent = `Last Processed: ${message.data.original_type} (ID: ${message.data.id || message.data.original_id || 'N/A'})`;
                        break;
                    default:
                        console.warn('MessageProcessor: Unhandled message type:', message.type, message);
                        document.getElementById('simulationStatus').textContent = `Unknown Message: ${message.type}`;
                }
            } catch (error) {
                console.error("MessageProcessor: Error processing message:", message, error);
                document.getElementById('simulationStatus').textContent = `Processing Error: ${error.message}`;
            }

            updateAllQueueDisplays();
            
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
