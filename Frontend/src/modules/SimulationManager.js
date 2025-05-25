// frontend/src/modules/SimulationManager.js

import { WebSocketManager } from './WebSocketManager.js';
import { fromBackendQueue, toBackendQueue } from '../app.js'; // Import queues from app.js

function startSimulation() {
    console.group('startSimulation');
    console.log('TRACE: startSimulation called!');
    
    // Clear queues before starting new simulation
    toBackendQueue.clear();
    fromBackendQueue.clear();
    console.log('Queues cleared before simulation start');

    const message = {
        type: 'command',
        command: 'start_simulation',
        parameters: {
            timestamp: new Date().toISOString()
        }
    };

    WebSocketManager.sendMessage(message);
    console.log('Sent WebSocket start command');
    document.getElementById('simulationStatus').textContent = 'Starting simulation...';
    document.getElementById('simulationStatus').style.color = 'orange';
    console.groupEnd();
}

function stopSimulation() {
    console.group('stopSimulation');
    console.log('TRACE: stopSimulation called!');

    const message = {
        type: 'command',
        command: 'stop_simulation',
        parameters: {
            timestamp: new Date().toISOString()
        }
    };

    WebSocketManager.sendMessage(message);
    console.log('Sent WebSocket stop command');
    document.getElementById('simulationStatus').textContent = 'Stopping simulation...';
    document.getElementById('simulationStatus').style.color = 'orange';
    console.groupEnd();
}

export { startSimulation, stopSimulation };
