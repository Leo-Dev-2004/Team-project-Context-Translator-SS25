import { UI } from './shared/index.js';
import './shared/index.css';

class ElectronMyElement extends UI {
  constructor() {
    super();
    this.platform = 'electron';
    this.isElectron = true;
    this.backendWs = null;
    console.log('Renderer: ⚙️ ElectronMyElement constructor called.');
  }

  // ### Lifecycle & UI Setup ###

  // Use firstUpdated for main application initialization
  async firstUpdated(changedProperties) {
    super.firstUpdated(changedProperties); // Call super.firstUpdated first
  // Hauptinitialisierung erfolgt über connectedCallback (Electron/WebSocket)
  // Entfernt: initializeApplication (nicht definiert) und doppelte Electron-Init
  }

  // connectedCallback is still useful for handlers, but main app init is in firstUpdated
  async connectedCallback() {
    super.connectedCallback();
    console.log('Renderer: ⚙️ connectedCallback entered.');
    await this._initializeElectron();
    this._initializeWebSocket();
    // this._attachActionListeners(); // DO NOT Attach listeners to buttons from ui.js. It will be duplicated as its already handled in ui.js
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.backendWs) {
      this.backendWs.close();
    }
    console.log('Renderer: ⚙️ disconnectedCallback: WebSocket connection cleaned up.');
  }

  _attachActionListeners() {
    console.log('Renderer: 💡 Attaching event listeners to action buttons...');
    
    const createSessionButton = this.shadowRoot.querySelector('#start-session-button');
    const joinSessionButton = this.shadowRoot.querySelector('#join-session-button');

    if (createSessionButton) {
      createSessionButton.addEventListener('click', () => this._startSession());
    } else {
      console.error("Renderer: ❌ 'Create Session' button not found.");
    }
    
    if (joinSessionButton) {
      joinSessionButton.addEventListener('click', () => this._joinSession());
    } else {
      console.error("Renderer: ❌ 'Join Session' button not found.");
    }

    console.log('Renderer: ✅ Event listeners successfully attached.');
  }

  // ### WebSocket & Messaging ###

  _initializeWebSocket() {
    const clientId = `frontend_renderer_${crypto.randomUUID()}`;
    const wsUrl = `ws://localhost:8000/ws/${clientId}`;
    console.log(`Renderer: ⚙️ Attempting WebSocket connection to ${wsUrl}...`);

    if (this.backendWs) this.backendWs.close();
    
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = () => {
      console.log('Renderer: ✅ WebSocket connection established.');
      this._performHandshake();
    };

    this.backendWs.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.type === 'system.queue_status_update') return;
        
        console.log(`Renderer: 💡 Message received from backend:`, message);

        if (message.type === 'session.created') {
            const code = message.payload.code;
            this.shadowRoot.querySelector('#session-code-input').value = code;
            
            const dialog = this.shadowRoot.querySelector('#session-dialog');
            const codeDisplay = this.shadowRoot.querySelector('#dialog-session-code');
            if (dialog && codeDisplay) {
                codeDisplay.textContent = code;
                dialog.show(); // Use .show() for non-modal
            }
        } else if (message.type === 'session.joined') {
            this._showNotification(`Successfully joined session ${message.payload.code}`, 'success');
        } else if (message.type === 'session.error') {
            this._showNotification(message.payload.error, 'error');
        } else if (message.type === 'explanation.new') {
            this._handleNewExplanation(message.payload.explanation);
        }
      } catch (error) {
        console.error('Renderer: ❌ Failed to parse message from backend:', error, event.data);
      }
    };

    this.backendWs.onerror = (error) => this._showNotification('WebSocket connection failed', 'error');
    this.backendWs.onclose = () => console.log('Renderer: ⚙️ WebSocket connection closed.');
  }

  async _performHandshake() {
    if (!window.electronAPI) {
        return console.error("Renderer: Electron API not available for handshake.");
    }
    const userSessionId = await window.electronAPI.getUserSessionId();
    this.userSessionId = userSessionId;
    
    if (!userSessionId) {
        return console.warn("Renderer: Could not retrieve User Session ID for handshake.");
    }

    console.log(`Renderer: 🚀 Sending "frontend.init" with User Session ID: ${userSessionId}`);
    const message = {
      id: crypto.randomUUID(),
      type: 'frontend.init',
      timestamp: Date.now() / 1000,
      payload: { user_session_id: userSessionId }
    };
    this.backendWs.send(JSON.stringify(message));
  }
  
  // ### Manual Request Logic ###
  _sendManualRequest() {
    const termInput = this.shadowRoot.querySelector('#manual-term-input');
    const term = (termInput?.value || this.manualTerm || '').trim();

    if (!term) {
      return this._showNotification('Please enter a term to explain', 'error');
    }
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('No connection to backend', 'error');
    }

    const message = {
      id: crypto.randomUUID(),
      type: 'manual.request',
      timestamp: Date.now() / 1000,
      payload: {
        term,
        context: term, // placeholder; could be extended to use selected text or domain
        user_session_id: this.userSessionId || null,
      },
    };

    try {
      this.backendWs.send(JSON.stringify(message));
      this._showNotification(`Requested explanation for "${term}"`, 'success');
      // Clear field in UI
      if (termInput) termInput.value = '';
      this.manualTerm = '';
      this.requestUpdate?.();
    } catch (e) {
      this._showNotification('Failed to send manual request', 'error');
    }
  }
  
  // ### Session Logic ###

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

  // ### Electron & Helper Functions ###
  
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

  _loadSettingsFromElectron(settings) {
    console.log('Renderer: Applying loaded settings:', settings);
    // Example: this.domainValue = settings.domain || '';
  }

  _handleNewExplanation(explanation) {
    console.log('Renderer: 📚 New explanation received:', explanation);

    // Import and use the explanationManager from the shared module
    import('./shared/explanation-manager.js').then(({ explanationManager }) => {
      if (explanation && explanation.term && explanation.content) {
        // Add explanation to the manager
        explanationManager.addExplanation(
          explanation.term,
          explanation.content,
          explanation.timestamp * 1000 // Convert to milliseconds if needed
        );

        // Show notification about new explanation
        this._showNotification(`New explanation: ${explanation.term}`, 'success');

        console.log(`Renderer: ✅ Added explanation for "${explanation.term}" to display`);
      } else {
        console.warn('Renderer: ⚠️ Invalid explanation data received:', explanation);
      }
    }).catch(error => {
      console.error('Renderer: ❌ Error importing explanation manager:', error);
    });
  }

  _showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed; bottom: 20px; left: 50%;
      transform: translateX(-50%); padding: 12px 24px;
      border-radius: 8px; color: white; font-family: 'Roboto', sans-serif;
      background-color: ${type === 'error' ? '#D32F2F' : '#2E7D32'};
      z-index: 1000; box-shadow: 0 4px 8px rgba(0,0,0,0.2);
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