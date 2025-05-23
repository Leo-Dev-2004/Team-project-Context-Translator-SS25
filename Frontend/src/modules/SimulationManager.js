// SimulationManager.js
import { toFrontendQueue, fromFrontendQueue, toBackendQueue, fromBackendQueue } from './MessageQueue.js';
import { updateQueueDisplay } from './QueueDisplay.js'; // To clear/update display
import { WebSocketManager } from './WebSocketManager.js'; // To check connection state

async function startSimulation() {
    console.log('TRACE: startSimulation called!');
    try {
        console.log('Starting simulation...');

        // Clear all queues first (good practice for new sim run)
        toFrontendQueue.clear();
        fromFrontendQueue.clear();
        toBackendQueue.clear();
        fromBackendQueue.clear();

        // Force immediate UI update with empty queues
        updateQueueDisplay({type: 'simulation_reset'});

        debugger; // Pause hier vor API-Aufruf
        const response = await fetch('http://localhost:8000/simulation/start', {
            mode: 'cors',
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Simulation started:', result);
        
        // Force UI update after starting simulation
        updateQueueDisplay(WebSocketManager.getLastReceivedMessage());

        if (WebSocketManager.isConnected && WebSocketManager.getState() === WebSocket.OPEN) {
            console.log("Waiting for backend confirmation via WebSocket...");
        } else {
            console.warn('WebSocket is not ready. Message not sent.');
        }
    } catch (error) {
        console.error('Failed to start simulation:', error);
        alert(`Failed to start simulation: ${error.message}`);
    }
}

async function stopSimulation() {
    console.log('TRACE: stopSimulation called!');
    try {
        const response = await fetch('http://localhost:8000/simulation/stop');
        const result = await response.json();
        console.log('Simulation stopped:', result);
        
        // Force UI update after stopping simulation
        updateQueueDisplay(WebSocketManager.getLastReceivedMessage());
        return result;
    } catch (error) {
        console.error('Failed to stop simulation:', error);
        throw error;
    }
}

export { startSimulation, stopSimulation };
