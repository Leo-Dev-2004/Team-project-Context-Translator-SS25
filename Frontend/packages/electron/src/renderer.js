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

  // ### WebSocket & Messaging ###

  /**
   * Initializes the WebSocket connection to the backend and sets up event listeners.
   */
  _initializeWebSocket() {
    const clientId = `frontend_renderer_${crypto.randomUUID()}`;
    const wsUrl = `ws://localhost:8000/ws/${clientId}`;
    console.log(`Renderer: ⚙️ Attempting WebSocket connection to ${wsUrl}...`);

    if (this.backendWs) this.backendWs.close();
    
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = () => console.log('Renderer: ✅ WebSocket connection established.');

    // REFACTORED: This handler now parses the message only once and filters noisy updates.
    this.backendWs.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        // Filter out noisy status updates from the main log
        if (message.type === 'system.queue_status_update') {
          return;
        }
        
        console.log(`Renderer: 💡 Message received from backend:`, message);

        if (message.type === 'session.created') {
            const code = message.payload.code;
            this._showNotification(`Session created! Code: ${code}`, 'success');
            const codeInput = this.shadowRoot.querySelector('#session-code-input');
            if (codeInput) codeInput.value = code;
        } else if (message.type === 'session.joined') {
            this._showNotification(`Successfully joined session ${message.payload.code}`, 'success');
        } else if (message.type === 'session.error') {
            this._showNotification(message.payload.error, 'error');
        }
      } catch (error) {
        console.error('Renderer: ❌ Failed to parse message from backend:', error, event.data);
      }
    };

    this.backendWs.onerror = (error) => this._showNotification('WebSocket connection failed', 'error');
    this.backendWs.onclose = () => console.log('Renderer: ⚙️ WebSocket connection closed.');
  }

  // ### Session Logic ###

  /**
   * Sends a message to the backend to create a new session.
   */
  _startSession() {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('No connection to backend', 'error');
    }
    console.log('Renderer: Sending "session.start" request...');
    const message = {
      id: crypto.randomUUID(),
      type: 'session.start',
      timestamp: Date.now() / 1000,
      payload: {},
    };
    this.backendWs.send(JSON.stringify(message));
  }

  /**
   * Sends a message to the backend to join an existing session with a code.
   */
  _joinSession() {
    const codeInput = this.shadowRoot.querySelector('#session-code-input');
    const code = codeInput ? codeInput.value.trim() : '';

    if (!code) return this._showNotification('Please enter a session code', 'error');
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('No connection to backend', 'error');
    }
    
    console.log(`Renderer: Sending "session.join" request with code ${code}...`);
    const message = {
      id: crypto.randomUUID(),
      type: 'session.join',
      timestamp: Date.now() / 1000,
      payload: { code: code },
    };
    this.backendWs.send(JSON.stringify(message));
  }
  
  // ### Lifecycle & UI Setup ###

  async connectedCallback() {
    super.connectedCallback();
    console.log('Renderer: ⚙️ connectedCallback entered.');
    await this._initializeElectron();
    this._initializeWebSocket();
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.backendWs) {
      this.backendWs.close();
    }
    console.log('Renderer: ⚙️ disconnectedCallback: WebSocket connection closed.');
  }

  _attachActionButtons() {
    console.log('Renderer: 💡 Attaching event listeners to action buttons...');
    const buttonContainer = this.shadowRoot.querySelector('div.action-buttons');
    
    if (!buttonContainer) {
      console.error("Renderer: ❌ Could not find the '.action-buttons' container.");
      return;
    }

    // Find the buttons that were rendered by ui.js
    const saveButton = this.shadowRoot.querySelector('md-filled-button'); // This is a bit fragile, better to add IDs in ui.js
    const resetButton = this.shadowRoot.querySelector('md-outlined-button');
    const createSessionButton = this.shadowRoot.querySelector('#start-session-button');
    const joinSessionButton = this.shadowRoot.querySelector('#join-session-button');

    // Attach our renderer-specific logic to them
    if (saveButton) {
      // Note: The UI class has a _saveSettings method. If you need special
      // logic in Electron, you would add the listener here.
      // For now, the one from ui.js is likely sufficient.
    }
    
    if (createSessionButton) {
      createSessionButton.addEventListener('click', () => this._startSession());
    }
    
    if (joinSessionButton) {
      joinSessionButton.addEventListener('click', () => this._joinSession());
    }

    console.log('Renderer: ✅ Event listeners successfully attached.');
  }
  
  // ### Electron & Helper Functions ###
  
  /**
   * Initializes Electron-specific APIs and loads saved settings.
   */
  async _initializeElectron() {
    console.log('Renderer: ⚙️ Initializing Electron APIs...');
    if (window.electronAPI) {
      try {
        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings);
        }
      } catch (error) {
        console.error('Renderer: ❌ Error during Electron initialization:', error);
      }
    } else {
      console.warn("Renderer: ⚠️ window.electronAPI not found. Not running in Electron?");
    }
  }

  /**
   * Applies settings loaded from the main process.
   * @param {object} settings The settings object.
   */
  _loadSettingsFromElectron(settings) {
    console.log('Renderer: Applying loaded settings:', settings);
    // Example: this.domainValue = settings.domain || '';
  }

  /**
   * Displays a temporary notification at the bottom of the screen.
   * @param {string} message The message to display.
   * @param {'success'|'error'} type The type of notification.
   */
  _showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed; bottom: 20px; left: 50%;
      transform: translateX(-50%); padding: 12px 24px;
      border-radius: 8px; color: white; font-family: 'Roboto', sans-serif;
      background-color: ${type === 'error' ? '#D32F2F' : '#2E7D32'};
      z-index: 1000; box-shadow: 0 4px 8px rgba(0,0,0,0.2);
      transition: opacity 0.3s ease-in-out;
    `;
    this.shadowRoot.appendChild(notification);
    setTimeout(() => notification.remove(), 4000);
  }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement);
} else {
  console.warn("Renderer: Custom element 'my-element' is already defined.");
}