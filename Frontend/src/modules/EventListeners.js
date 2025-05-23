// EventListeners.js
import { startSimulation, stopSimulation } from './SimulationManager.js';
import { WebSocketManager } from './WebSocketManager.js';
import { updateQueueCounters, updateQueueDisplay } from './QueueDisplay.js'; // updateQueueDisplay also needs lastMessage
import { toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue } from './MessageQueue.js';

// This function handles the async processing of backend messages
async function processBackendMessages() {
    console.group('processBackendMessages');
    console.log("Starting backend message processing loop");
    console.log("Initial queue state:", {
        size: fromBackendQueue.size(),
        items: fromBackendQueue.queue.map(i => i.type)
    });
    console.groupEnd();

    while (true) {
        try {
            console.groupCollapsed(`processBackendMessages iteration`);
            debugger; // Pause vor dequeue
            console.log("Waiting for message from fromBackendQueue...");
            console.log("Current queue state:", {
                size: fromBackendQueue.size(),
                items: fromBackendQueue.queue.map(i => i.type)
            });
            console.log("DEBUG: Current fromBackendQueue state:", {
                size: fromBackendQueue.size(),
                items: fromBackendQueue.queue.map(i => i.type)
            });
            const message = await fromBackendQueue.dequeue();
            console.log("DEBUG: processBackendMessages: Dequeued message:", {
                type: message.type,
                timestamp: message.timestamp,
                _debug: message._debug
            });
            console.groupCollapsed(`Processing backend message [${message.type}]`);
            console.log('Full message details:', JSON.stringify(message, null, 2));
            console.log('Raw message:', message);

            const processingStart = Date.now();
            const queueTime = processingStart - (message._debug?.received || processingStart);

            let processedMessage = {...message};

            if (message.type === 'status_update') {
                processedMessage = {
                    ...message,
                    _debug: {
                        ...message._debug,
                        processed: true,
                        processingTime: Date.now() - processingStart,
                        queueTime: queueTime
                    }
                };
                toFrontendQueue.enqueue(processedMessage);
            } else if (message.type === 'sys_init') {
                console.log('System initialization received');
                toFrontendQueue.enqueue(processedMessage);
            } else if (message.type === 'simulation_update') {
                console.group('DEBUG: Processing simulation_update');
                console.log('DEBUG: Original message:', JSON.stringify(message, null, 2));

                processedMessage = {
                    ...message,
                    _debug: {
                        ...message._debug,
                        processed: true,
                        processingTime: Date.now() - processingStart,
                        queueTime: queueTime,
                        processedAt: new Date().toISOString(),
                        processingStage: 'frontend-processor'
                    }
                };

                console.log('DEBUG: Processed message:', JSON.stringify(processedMessage, null, 2));

                console.log('DEBUG: Enqueuing to toFrontendQueue...');
                toFrontendQueue.enqueue(processedMessage);

                console.log("DEBUG: toFrontendQueue state:", {
                    size: toFrontendQueue.size(),
                    items: toFrontendQueue.queue.map(i => ({
                        type: i.type,
                        timestamp: i.timestamp,
                        _debug: i._debug?.processingStage
                    }))
                });

                if (message.data?.debugBreak) {
                    debugger;
                }
                console.groupEnd();
            }

            // Need to pass the latest lastMessage to updateQueueDisplay if it's used there
            // For now, WebSocketManager.getLastReceivedMessage() could provide it
            updateQueueDisplay(WebSocketManager.getLastReceivedMessage()); // Pass lastMessage
            console.log('Message processed in', Date.now() - processingStart, 'ms');
            console.groupEnd();
        } catch (error) {
            console.error('Error processing message:', error);
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
}

// Function to send a test message (for debugging display)
function sendTestMessage() {
    console.log("TRACE: sendTestMessage called!");
    console.log("Attempting to send test message...");
    const testMessage = {
        type: "test_message",
        data: {
            content: "This is a test message from the frontend.",
            timestamp: Date.now()
        },
        _debug: {
            sent: Date.now(),
            queue: 'fromFrontend'
        }
    };

    debugger; // Pause hier vor Enqueue
    fromFrontendQueue.enqueue(testMessage);
    console.log("DEBUG: Test message enqueued to fromFrontendQueue. Current size:", fromFrontendQueue.size(), "Content:", fromFrontendQueue.queue);
    // debugger; // Keep this debugger for now for test message flow

    updateQueueDisplay(WebSocketManager.getLastReceivedMessage()); // Pass lastMessage
    console.log("DEBUG: updateQueueDisplay triggered for test message.");
}


function setupQueueListeners() {
    console.group('DEBUG: Setting up queue listeners');

    const queueNames = {
        toFrontendQueue: 'toFrontend',
        fromFrontendQueue: 'fromFrontend',
        toBackendQueue: 'toBackend',
        fromBackendQueue: 'fromBackend'
    };

    Object.entries({toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue}).forEach(([varName, queue]) => {
        const queueName = queueNames[varName];
        console.log(`DEBUG: Adding listener for ${queueName}Queue`);

        queue.addListener(() => {
            console.groupCollapsed(`DEBUG: ${queueName}Queue changed`);
            console.log('Queue state:', {
                size: queue.size(),
                items: queue.queue.map(i => i.type)
            });

            // The main updateQueueDisplay call for ALL queue updates is in app.js
            // This listener could trigger it if it's specific to this queue type,
            // but the centralized update in app.js is generally preferred.
            // If you want granular updates, uncomment:
            // if (queueName === 'toFrontend') {
            //     console.log('DEBUG: Triggering display update from listener');
            //     updateQueueDisplay(WebSocketManager.getLastReceivedMessage());
            // }

            console.groupEnd();
        });
    });

    console.groupEnd();
}


// Export the main initialization function
export function initializeEventListeners() {
    console.group('DOMContentLoaded');
    console.log('Initializing frontend...');

    document.getElementById('startSim').addEventListener('click', startSimulation);
    console.log('Event listener added for #startSim');
    document.getElementById('stopSim').addEventListener('click', stopSimulation);
    console.log('Event listener added for #stopSim');
    document.getElementById('testButton').addEventListener('click', sendTestMessage);
    console.log('Event listener added for #testButton');
    console.log('Button handlers configured');

    setupQueueListeners();

    // No need to connect WebSocketManager here, it's done in app.js and triggers processBackendMessages
    // via 'websocket-ack' event.

    document.addEventListener('websocket-ack', (e) => {
        console.group('websocket-ack Event');
        console.log('WebSocket connection acknowledged by server');
        console.log('Event details:', e);
        
        const statusElement = document.getElementById('connectionStatus');
        statusElement.textContent = 'Connected';
        statusElement.style.color = 'green';
        statusElement.style.fontWeight = 'bold';

        if (!window._backendProcessorStarted) {
            console.log("Starting backend message processor...");
            window._backendProcessorStarted = true;
            console.log("Calling processBackendMessages()");
            debugger; // Pause vor Prozessstart
            processBackendMessages().catch(e => {
                console.error("Error in processBackendMessages:", e);
            });
        } else {
            console.warn("Backend message processor already running!");
        }
        console.groupEnd();
    });

    console.groupEnd();
}
