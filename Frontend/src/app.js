// Haupt-Einstiegspunkt der Anwendung
import { WebSocketManager } from './modules/WebSocketManager.js';
import { SimulationManager } from './modules/SimulationManager.js';
import { MessageQueue } from './modules/MessageQueue.js';
import { QueueDisplay } from './modules/QueueDisplay.js';
import { setupEventListeners } from './modules/EventListeners.js';

// Globale Variablen für die Queues
export const toFrontendQueue = new MessageQueue('toFrontend');
export const fromFrontendQueue = new MessageQueue('fromFrontend');
export const toBackendQueue = new MessageQueue('toBackend');
export const fromBackendQueue = new MessageQueue('fromBackend');

// WebSocket Manager initialisieren
const wsManager = new WebSocketManager();

// Queue Display initialisieren
const queueDisplay = new QueueDisplay({
    toFrontendQueue,
    fromFrontendQueue,
    toBackendQueue,
    fromBackendQueue
});

// Simulation Manager initialisieren
const simManager = new SimulationManager(wsManager);

// Event Listener registrieren
setupEventListeners({
    wsManager,
    simManager,
    queueDisplay
});

// Initiale UI-Aktualisierung
queueDisplay.updateAllDisplays();

// Verbindung zum Backend herstellen
wsManager.connect('ws://localhost:8000/ws')
    .then(() => {
        console.log('WebSocket verbunden');
        document.getElementById('connectionStatus').textContent = 'Connected';
    })
    .catch(err => {
        console.error('WebSocket Verbindungsfehler:', err);
        document.getElementById('connectionStatus').textContent = 'Error: ' + err.message;
    });

// Hilfsfunktion für Testzwecke
window.sendTestMessage = function() {
    wsManager.sendMessage({
        type: 'test',
        content: 'Testnachricht vom Frontend',
        timestamp: new Date().toISOString()
    });
};
