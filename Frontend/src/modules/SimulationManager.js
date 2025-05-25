// frontend/src/modules/SimulationManager.js

import WebSocketManager from './WebSocketManager.js';
import { fromBackendQueue, toBackendQueue } from '../app.js'; // Import queues from app.js

async function startSimulation() {
    console.group('startSimulation');
    console.log('TRACE: startSimulation called!');
    try {
        // Clear queues before starting new simulation
        toBackendQueue.clear();
        fromBackendQueue.clear();
        console.log('Queues cleared before simulation start');

        const response = await fetch('/api/simulation/start', {
            method: 'GET',
            mode: 'cors',
            credentials: 'include'
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log('Simulation start response:', result);
        document.getElementById('simulationStatus').textContent = 'Simulation started';
        document.getElementById('simulationStatus').style.color = 'green';

    } catch (error) {
        console.error('Failed to start simulation:', error);
        let errorMsg = error.message;
        if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            errorMsg = 'Backend server not reachable. Is it running?';
        }
        document.getElementById('simulationStatus').textContent = `Failed to start: ${errorMsg}`;
        document.getElementById('simulationStatus').style.color = 'red';
    }
    console.groupEnd();
}

async function stopSimulation() {
    console.group('stopSimulation');
    console.log('TRACE: stopSimulation called!');
    try {
        // First try graceful stop via API
        const response = await fetch('/api/simulation/stop', {
            method: 'GET',
            mode: 'cors', 
            credentials: 'include'
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log('Simulation stop response:', result);
        document.getElementById('simulationStatus').textContent = 'Simulation stopped';
        document.getElementById('simulationStatus').style.color = 'red';

    } catch (error) {
        console.error('Failed to stop simulation:', error);
        document.getElementById('simulationStatus').textContent = `Failed to stop: ${error.message}`;
    }
    console.groupEnd();
}

export { startSimulation, stopSimulation };
