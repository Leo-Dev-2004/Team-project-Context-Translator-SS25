// Frontend/src/app.js

import { MessagingService } from './modules/MessagingService.js';
import { setupEventListeners } from './modules/EventListeners.js';
import { updateSystemLog, updateQueueDisplay } from './modules/QueueDisplay.js';

// --- Application Initialization Logic ---
document.addEventListener('DOMContentLoaded', () => {
    console.log('app.js: DOMContentLoaded (first time)');

    // 1. Generate Client ID
    const clientId = `client_${Date.now()}${Math.random().toString(36).substring(2, 9)}`;
    updateSystemLog(`Frontend Client ID: ${clientId}`);

    // 2. Initialize the central MessagingService
    MessagingService.initialize(clientId);
    console.log('app.js: MessagingService initialized.');

    // 3. Get references to the queues from MessagingService
    const toBackendQueue = MessagingService.getToBackendQueue();
    const fromBackendQueue = MessagingService.getFromBackendQueue();
    const frontendDisplayQueue = MessagingService.getFrontendDisplayQueue();
    const frontendActionQueue = MessagingService.getFrontendActionQueue(); // If you need this later

    // 4. Set up Event Listeners, passing the necessary queues/service
    setupEventListeners({
        messagingService: MessagingService, // Pass the entire service
        toBackendQueue, // Still pass directly if EventListeners enqueues directly (less ideal)
        fromBackendQueue, // Still pass directly if EventListeners dequeues directly (current setup)
        frontendDisplayQueue,
        frontendActionQueue
    });
    console.log('app.js: EventListeners set up with MessagingService and queues.');

    // --- Helper function to send a burst of test messages ---
    const sendBurstTestMessages = async () => {
        await new Promise(resolve => setTimeout(resolve, 500));
        console.log('app.js: Sending burst of test messages...');
        updateSystemLog('Sending a burst of 15 test messages...');

        for (let i = 0; i < 15; i++) {
            MessagingService.sendToBackend(
                'test.message',
                { content: `Frontend burst message ${i + 1}`, timestamp: Date.now() / 1000 }
            );
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        console.log('app.js: Finished enqueuing burst test messages.');
        updateSystemLog('Finished enqueuing 15 test messages.');
    };

    // NEW: Event Listener for Send Test Settings Button (using MessagingService)
    const sendTestSettingsBtn = document.getElementById('sendTestSettingsBtn');
    if (sendTestSettingsBtn) {
        sendTestSettingsBtn.addEventListener('click', () => {
            console.log('app.js: "Send Test Settings" button clicked.');
            updateSystemLog('Attempting to send test settings message...');

            MessagingService.sendToBackend(
                'update_settings',
                {
                    theme: 'dark_mode',
                    notifications: true,
                    language: 'en-US',
                    level: Math.floor(Math.random() * 10) + 1
                }
            );
            updateSystemLog('Test settings message enqueued via MessagingService.');
        });
    }

    // --- Trigger the burst of test messages after a short delay ---
    setTimeout(() => sendBurstTestMessages(), 2500);

    // --- Queue Display Updates (subscribe to the queues) ---
    // You subscribe to the queues obtained from MessagingService
    toBackendQueue.subscribe((queueName, size, items) => {
        updateQueueDisplay(queueName, size, items);
    });
    fromBackendQueue.subscribe((queueName, size, items) => {
        updateQueueDisplay(queueName, size, items);
    });
    // If you want to visualize frontendDisplayQueue:
    frontendDisplayQueue.subscribe((queueName, size, items) => {
        // This queue is processed internally, so you might not want to show it in the main flow
        // or just show its size and not individual messages unless debug
        // For now, let's keep it separate from the main flow visualization.
        // updateQueueDisplay(queueName, size, items);
    });


    console.log('app.js: Application initialization complete.');
});