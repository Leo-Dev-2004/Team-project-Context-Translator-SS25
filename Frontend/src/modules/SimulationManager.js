// frontend/src/modules/SimulationManager.js

import { WebSocketManager } from './WebSocketManager.js';
import { fromBackendQueue, toBackendQueue } from '../app.js'; // Import queues from app.js

async function startSimulation() {
    console.group('startSimulation');
    console.log('TRACE: startSimulation called!');
    try {
        const response = await fetch('http://localhost:8000/simulation/start', {
            method: 'POST', // Assuming it's a POST to start/stop
            mode: 'cors',
            credentials: 'include'
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log('Simulation start response:', result);
        // WebSocketManager.sendMessage({ type: 'simulation_started', content: result }); // Or handle via QueueForwarder

    } catch (error) {
        console.error('Failed to start simulation:', error);
        document.getElementById('simulationStatus').textContent = `Failed to start: ${error.message}`;
    }
    console.groupEnd();
}

async function stopSimulation() {
    console.group('stopSimulation');
    console.log('TRACE: stopSimulation called!');
    try {
        const response = await fetch('http://localhost:8000/simulation/stop', {
            method: 'POST', // Assuming it's a POST
            mode: 'cors',
            credentials: 'include'
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log('Simulation stop response:', result);
        // WebSocketManager.sendMessage({ type: 'simulation_stopped', content: result }); // Or handle via QueueForwarder

    } catch (error) {
        console.error('Failed to stop simulation:', error);
        document.getElementById('simulationStatus').textContent = `Failed to stop: ${error.message}`;
    }
    console.groupEnd();
}

export { startSimulation, stopSimulation };