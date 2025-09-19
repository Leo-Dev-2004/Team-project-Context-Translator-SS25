import { UI } from './shared/index.js';
import { explanationManager } from './shared/explanation-manager.js';
import './shared/index.css';

class ElectronMyElement extends UI {
  constructor() {
    super();
    this.platform = 'electron';
    this.isElectron = true;
    this.backendWs = null;
    this.activeNotifications = new Set(); // Track active notifications
    this.maxNotifications = 3; // Limit concurrent notifications
    this.messageQueue = []; // Queue for processing messages
    this.isProcessingMessages = false; // Flag to prevent concurrent processing
    this.lastExplanationTime = 0; // Throttle explanations
    this.explanationThrottleMs = 1000; // Minimum time between explanation notifications
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
    
    // Clean up WebSocket connection
    if (this.backendWs) {
      this.backendWs.close();
      this.backendWs = null;
    }
    
    // Clear message queue
    this.messageQueue = [];
    this.isProcessingMessages = false;
    
    // Clean up active notifications
    this.activeNotifications.forEach(notification => {
      if (notification.parentNode) {
        notification.remove();
      }
    });
    this.activeNotifications.clear();
    
    console.log('Renderer: ⚙️ disconnectedCallback: All resources cleaned up.');
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

  async _processMessageQueue() {
    if (this.isProcessingMessages || this.messageQueue.length === 0) {
      return;
    }

    this.isProcessingMessages = true;

    try {
      while (this.messageQueue.length > 0) {
        const message = this.messageQueue.shift();
        console.log(`Renderer: 💡 Processing message from backend:`, message);

        await this._handleMessage(message);

        // Small delay to prevent blocking the UI thread
        if (this.messageQueue.length > 0) {
          await new Promise(resolve => setTimeout(resolve, 10));
        }
      }
    } catch (error) {
      console.error('Renderer: ❌ Error processing message queue:', error);
    } finally {
      this.isProcessingMessages = false;
    }
  }

  async _handleMessage(message) {
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
  }

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
        
        // Add message to queue for processing
        this.messageQueue.push(message);
        this._processMessageQueue();
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

    if (explanation && explanation.term && explanation.content) {
      // Add explanation to the manager
      const confidence = typeof explanation.confidence === 'number' ? explanation.confidence : null;
      explanationManager.addExplanation(
        explanation.term,
        explanation.content,
        explanation.timestamp * 1000, // Convert to milliseconds if needed
        confidence
      );

      // Throttle notification display to prevent notification spam
      const now = Date.now();
      if (now - this.lastExplanationTime >= this.explanationThrottleMs) {
        this._showNotification(`New explanation: ${explanation.term}`, 'success');
        this.lastExplanationTime = now;
      }

      console.log(`Renderer: ✅ Added explanation for "${explanation.term}" to display`);
    } else {
      console.warn('Renderer: ⚠️ Invalid explanation data received:', explanation);
    }
  }

  _showNotification(message, type = 'success') {
    // Remove oldest notification if at limit
    if (this.activeNotifications.size >= this.maxNotifications) {
      const oldestNotification = this.activeNotifications.values().next().value;
      if (oldestNotification && oldestNotification.parentNode) {
        oldestNotification.remove();
        this.activeNotifications.delete(oldestNotification);
      }
    }

    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed; bottom: ${20 + (this.activeNotifications.size * 60)}px; left: 50%;
      transform: translateX(-50%); padding: 12px 24px;
      border-radius: 8px; color: white; font-family: 'Roboto', sans-serif;
      background-color: ${type === 'error' ? '#D32F2F' : '#2E7D32'};
      z-index: 1000; box-shadow: 0 4px 8px rgba(0,0,0,0.2);
      transition: all 0.3s ease;
    `;
    
    this.shadowRoot.appendChild(notification);
    this.activeNotifications.add(notification);
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
      this.activeNotifications.delete(notification);
    }, 4000);
  }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement);
} else {
  console.warn("Renderer: Custom element 'my-element' is already defined.");
}