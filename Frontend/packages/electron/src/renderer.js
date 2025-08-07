// renderer.js (Final Clean Version)

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

    if (this.backendWs) this.backendWs.close();
    
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = () => console.log('Renderer: ✅ WebSocket-Verbindung zum Backend erfolgreich hergestellt.');

    this.backendWs.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type !== 'system.queue_status_update') {
        console.log(`Renderer: 💡 Nachricht vom Backend empfangen:`, event.data);
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === 'session.created') {
              const code = message.payload.code;
              this._showNotification(`Session erstellt! Code: ${code}`, 'success');
              this.shadowRoot.querySelector('#session-code-input').value = code;
          } else if (message.type === 'session.joined') {
              this._showNotification(`Erfolgreich beigetreten zu Session ${message.payload.code}`, 'success');
          } else if (message.type === 'session.error') {
              this._showNotification(message.payload.error, 'error');
          } // ... other message handlers
        } catch (error) {
          console.error('Renderer: ❌ Fehler beim Parsen der Backend-Nachricht:', error);
        }
      }
    };

    this.backendWs.onerror = (error) => this._showNotification('WebSocket-Verbindung fehlgeschlagen', 'error');
    this.backendWs.onclose = () => console.log('Renderer: ⚙️ WebSocket-Verbindung geschlossen.');
  }

  // ### Session-Logik ###
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
  
  // ### Lifecycle & UI-Setup ###
  async connectedCallback() {
    console.log('Renderer: ⚙️ connectedCallback entered.');
    super.connectedCallback();
    await this._initializeElectron();
    this._initializeWebSocket();
    this._attachActionButtons();
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }

  _attachActionButtons() {
    const buttonContainer = this.shadowRoot.querySelector('div.action-buttons');
    if (buttonContainer) {
      buttonContainer.innerHTML = ''; 
      
      const createButton = document.createElement('md-filled-button');
      createButton.textContent = 'Session erstellen';
      createButton.addEventListener('click', () => this._startSession());

      const sessionCodeInput = document.createElement('md-outlined-text-field');
      sessionCodeInput.label = 'Session Code';
      sessionCodeInput.id = 'session-code-input';
      sessionCodeInput.style.cssText = `margin: 0 12px;`;

      const joinButton = document.createElement('md-outlined-button');
      joinButton.textContent = 'Session beitreten';
      joinButton.addEventListener('click', () => this._joinSession());
      
      buttonContainer.append(createButton, sessionCodeInput, joinButton);
    }
  }
  
  // ### Electron & Hilfsfunktionen ###
  async _initializeElectron() { /* ... unverändert ... */ }
  _loadSettingsFromElectron(settings) { /* ... unverändert ... */ }
  _showNotification(message, type = 'success') { /* ... unverändert ... */ }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement);
} else {
  console.warn("Renderer: Custom element 'my-element' bereits definiert.");
}