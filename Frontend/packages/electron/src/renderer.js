// renderer.js (Vollständige Implementierung)

import { UI } from '../../shared/src/index.js';
import '../../shared/src/index.css';

class ElectronMyElement extends UI {
  constructor() {
    super();
    this.platform = 'electron';
    this.isElectron = true;
    this.backendWs = null;
    console.log('Renderer: ⚙️ ElectronMyElement constructor called.');
  }

  // ### WebSocket & Nachrichten ###

  _initializeWebSocket() {
    const clientId = `frontend_renderer_${crypto.randomUUID()}`;
    const wsUrl = `ws://localhost:8000/ws/${clientId}`;
    console.log(`Renderer: ⚙️ Versuche, WebSocket-Verbindung zu ${wsUrl} aufzubauen...`);

    if (this.backendWs) {
      this.backendWs.close();
    }
    
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = (event) => {
      console.log('Renderer: ✅ WebSocket-Verbindung zum Backend erfolgreich hergestellt.');
    };

    this.backendWs.onmessage = (event) => {
      console.log(`Renderer: 💡 Nachricht vom Backend empfangen:`, event.data);
      try {
        const message = JSON.parse(event.data);
        
        // GEMERGED: Behandelt jetzt alle Nachrichtentypen
        if (message.type === 'session.created') {
            const code = message.payload.code;
            this._showNotification(`Session erstellt! Code: ${code}`, 'success');
            this.shadowRoot.querySelector('#session-code-input').value = code;
        } else if (message.type === 'session.joined') {
            this._showNotification(`Erfolgreich beigetreten zu Session ${message.payload.code}`, 'success');
        } else if (message.type === 'session.error') {
            this._showNotification(message.payload.error, 'error');
        } else if (message.type === 'translation.result') {
          this.addTranslation(message.payload); // Annahme aus UI-Basisklasse
        } else if (message.type === 'stt.transcription') {
          this.addTranscription(message.payload); // Annahme aus UI-Basisklasse
        }
      } catch (error) {
        console.error('Renderer: ❌ Fehler beim Parsen der Backend-Nachricht:', error);
      }
    };

    this.backendWs.onerror = (error) => {
      console.error('Renderer: ❌ WebSocket-Fehler:', error);
      this._showNotification('WebSocket-Verbindung fehlgeschlagen', 'error');
    };

    this.backendWs.onclose = (event) => {
      console.log('Renderer: ⚙️ WebSocket-Verbindung geschlossen.', `Code: ${event.code}`, `Grund: ${event.reason}`);
      this.backendWs = null;
    };
  }

  // ### Session & Demo Logik ###

  _startSession() {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('Keine Verbindung zum Backend', 'error');
    }
    console.log('Renderer: Sende "session.start"-Anfrage...');
    this.backendWs.send(JSON.stringify({ type: 'session.start' }));
  }

  _joinSession() {
    const codeInput = this.shadowRoot.querySelector('#session-code-input');
    const code = codeInput ? codeInput.value.trim() : '';

    if (!code) return this._showNotification('Bitte einen Session-Code eingeben', 'error');
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('Keine Verbindung zum Backend', 'error');
    }
    
    console.log(`Renderer: Sende "session.join"-Anfrage mit Code ${code}...`);
    this.backendWs.send(JSON.stringify({ type: 'session.join', payload: { code } }));
  }
  
  sendDemoSTTMessage(text) {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('Keine Verbindung zum Backend', 'error');
    }
    const message = { type: 'stt.transcription', payload: { text } };
    this.backendWs.send(JSON.stringify(message));
    console.log(`Renderer: 💡 Demo-Nachricht gesendet: ${text}`);
  }

  // ### Lifecycle & UI-Setup ###

  async connectedCallback() {
    console.log('Renderer: ⚙️ connectedCallback entered.');
    super.connectedCallback();

    await this._initializeElectron();
    this._initializeWebSocket();
    await this._runCommunicationTests();
    
    // Ruft die neue, zentrale Methode zum Anhängen der Buttons auf.
    this._attachActionButtons();
    
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }

  _attachActionButtons() {
    console.log('Renderer: 💡 Hänge Action-Buttons an die UI an...');
    const buttonContainer = this.shadowRoot.querySelector('div.action-buttons');
    
    if (buttonContainer) {
      // Leert den Container, um doppelte Buttons zu vermeiden
      buttonContainer.innerHTML = ''; 

      // Demo-Nachricht Button
      const demoButton = document.createElement('md-filled-button');
      demoButton.textContent = 'Sende Demo-Nachricht';
      demoButton.addEventListener('click', () => {
        this.sendDemoSTTMessage('Das ist eine manuell ausgelöste Testnachricht.');
      });

      // Session Erstellen Button
      const createButton = document.createElement('md-filled-button');
      createButton.textContent = 'Session erstellen';
      createButton.style.cssText = `margin-left: 20px;`;
      createButton.addEventListener('click', () => this._startSession());

      // Session Code Eingabefeld
      const sessionCodeInput = document.createElement('md-outlined-text-field');
      sessionCodeInput.label = 'Session Code';
      sessionCodeInput.id = 'session-code-input';
      sessionCodeInput.style.cssText = `margin: 0 12px;`;

      // Session Beitreten Button
      const joinButton = document.createElement('md-outlined-button');
      joinButton.textContent = 'Session beitreten';
      joinButton.addEventListener('click', () => this._joinSession());
      
      buttonContainer.append(demoButton, createButton, sessionCodeInput, joinButton);
      console.log('Renderer: ✅ Action-Buttons erfolgreich angehängt.');
    } else {
      console.error('Renderer: ❌ Button-Container mit Klasse "action-buttons" nicht gefunden.');
    }
  }
  
  // ### Electron & Hilfsfunktionen ###

  async _initializeElectron() {
    console.log('Renderer: ⚙️ _initializeElectron entered.');
    if (window.electronAPI) {
      try {
        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings);
        }
      } catch (error) {
        console.error('Renderer: ❌ Fehler bei der Electron-Initialisierung:', error);
      }
    }
  }
  
  async _runCommunicationTests() {
    console.log('Renderer: --- Starting Electron IPC & WS Communication Tests ---');
    await this._testElectronIPC();
    try {
        await this._testBackendWebSocket();
        console.log('Renderer: --- Communication Tests Finished ---');
    } catch (error) {
        console.error('Renderer: --- WS Communication Tests Failed ---', error);
    }
  }

  async _testElectronIPC() {
    try {
      const version = await window.electronAPI.getAppVersion();
      console.log(`[IPC Test] App Version: ${version} (OK)`);
    } catch (e) {
      console.error('[IPC Test] Failed:', e);
    }
  }

  async _testBackendWebSocket() {
    return new Promise((resolve, reject) => {
      const interval = setInterval(() => {
        if (this.backendWs && this.backendWs.readyState === WebSocket.OPEN) {
          clearInterval(interval);
          console.log('[WS Test] Connection is open. (OK)');
          resolve();
        }
      }, 100);
      setTimeout(() => {
        clearInterval(interval);
        reject(new Error('WebSocket connection timeout'));
      }, 5000);
    });
  }

  _loadSettingsFromElectron(settings) {
    console.log('Renderer: Wende geladene Einstellungen an:', settings);
  }

  _showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed; bottom: 20px; left: 50%;
      transform: translateX(-50%); padding: 10px 20px;
      border-radius: 5px; color: white;
      background-color: ${type === 'error' ? '#D32F2F' : '#388E3C'};
      z-index: 1000; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    `;
    this.shadowRoot.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
  }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement);
} else {
  console.warn("Renderer: Custom element 'my-element' bereits definiert. Überspringe Neuregistrierung.");
}