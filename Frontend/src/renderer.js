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
    this.notificationCleanupTimeouts = new Set();
    this.audioStream = null;
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
    this._initializeMicrophone();

    this._attachActionListeners(); // DO NOT Attach listeners to buttons from ui.js. It will be duplicated as its already handled in ui.js
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

    // Clear any pending notification timeouts
    this.notificationCleanupTimeouts.forEach(timeoutId => clearTimeout(timeoutId));
    this.notificationCleanupTimeouts.clear();
    // stop audio stream tracks
    if (this.audioStream) {
    this.audioStream.getTracks().forEach(track => track.stop());
  }
    console.log('Renderer: ⚙️ disconnectedCallback: WebSocket connection cleaned up.');
  }

    // Initialize microphone access and status
  async _initializeMicrophone() {
  console.log('Renderer: 🎤 Try to get access to the microphone...');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    this.audioStream = stream; // Store the stream

    const audioTrack = stream.getAudioTracks()[0];
    if (!audioTrack) {
      // Should not happen, but better safe than sorry
      this.updateMicrophoneStatus('trouble');
      return;
    }

    // Event Listener für Mute/Unmute hinzufügen
    audioTrack.onmute = () => {
      console.log('Renderer: 🎤 Microphone is muted.');
      this.updateMicrophoneStatus('muted');
    };

    audioTrack.onunmute = () => {
      console.log('Renderer: 🎤 Microphone is unmuted.');
      this.updateMicrophoneStatus('connected');
    };

    // Initial status check in case the microphone is already muted at startup
    if (audioTrack.muted) {
      this.updateMicrophoneStatus('muted');
    } else {
      this.updateMicrophoneStatus('connected');
    }

  } catch (error) {
    // Here we catch errors
    console.error('Renderer: ❌ Error with microphone access:', error.name, error.message);

    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
      // The user denied access to the microphone
      console.warn('Renderer: 🎤 Microphone access denied by user.');
      this.updateMicrophoneStatus('denied'); // Clear status for "denied"

    } else if (error.name === 'NotFoundError') {
      // No microphone found on the system
      console.warn('Renderer: 🎤 No microphone found.');
      this.updateMicrophoneStatus('not-found'); // Clear status for "not found"

    } else {
      // Other unexpected errors (e.g. hardware issues)
      console.error('Renderer: 🎤 An unexpected error occurred.');
      this.updateMicrophoneStatus('trouble'); // General error status
    }
    }
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

  // Updates status indicators in the status bar (Server = Backend)
  updateServerStatus(newStatus) {
      this.serverStatus = newStatus;
      console.log(`Renderer: 📡 Server-Status updated to: "${newStatus}".`);
  }
  
  // Updates status indicators in the status bar (Microphone)
  updateMicrophoneStatus(newStatus) {
    this.microphoneStatus = newStatus;
    console.log(`Renderer: 🎤 Microphone-Status updated to: "${newStatus}".`);
    
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
    } else if (message.type === 'explanation.retry') {
      this._handleRetryExplanation(message.payload.explanation);
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
      this.updateServerStatus('connected');
      this._performHandshake();
    };

    this.backendWs.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        // Skip high-frequency status updates to prevent event loop congestion
        if (message.type === 'system.queue_status_update') return;
        
        // Add message to queue for processing
        this.messageQueue.push(message);
        this._processMessageQueue();
      } catch (error) {
        console.error('Renderer: ❌ Failed to parse message from backend:', error, event.data);
      }
    };

    this.backendWs.onerror = (error) => {
      this.updateServerStatus('trouble');
      this._showNotification('WebSocket connection failed', 'error');
    };
    this.backendWs.onclose = () => {
      this.updateServerStatus('disconnected');
      console.log('Renderer: ⚙️ WebSocket connection closed.');
    };
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
        domain: this.domainValue || '', // Include domain context for AI processing
        explanation_style: this.explanationStyle || 'detailed', // Include explanation style preference
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
    if (settings.domain) this.domainValue = settings.domain;
    if (settings.explanationStyle) this.explanationStyle = settings.explanationStyle;
  }

  // Override settings methods from base UI class
  async _saveSettings() {
    if (!window.electronAPI) {
      return console.error("Renderer: window.electronAPI not available for saving settings.");
    }

    const settings = {
      domain: this.domainValue,
      explanationStyle: this.explanationStyle
    };

    try {
      const result = await window.electronAPI.saveSettings(settings);
      if (result.success) {
        this._showNotification('Settings saved successfully', 'success');
      } else {
        this._showNotification('Failed to save settings', 'error');
      }
    } catch (error) {
      console.error('Renderer: Error saving settings:', error);
      this._showNotification('Error saving settings', 'error');
    }
    if (settings.explanationStyle) {
      this.explanationStyle = settings.explanationStyle;
    }
  }

  _resetSettings() {
    super._resetSettings(); // Reset the base values
    this._saveSettings(); // Save the reset values
  }

  // Override regenerate handler
  _handleRegenerate(explanation) {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('No connection to backend', 'error');
    }

    console.log('Renderer: Sending regenerate request for explanation:', explanation);
    
    const message = {
      id: crypto.randomUUID(),
      type: 'explanation.retry',
      timestamp: Date.now() / 1000,
      payload: {
        original_explanation_id: explanation.id,
        term: explanation.title,
        context: explanation.title, // Use the term as context or could be extended
        user_session_id: this.userSessionId || null,
        explanation_style: this.explanationStyle
      },
    };

    try {
      this.backendWs.send(JSON.stringify(message));
      this._showNotification(`Regenerating explanation for "${explanation.title}"`, 'success');
    } catch (error) {
      console.error('Renderer: Error sending regenerate request:', error);
      this._showNotification('Failed to send regenerate request', 'error');
    }
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

  _handleRetryExplanation(explanation) {
    console.log('Renderer: 🔄 Retry explanation received:', explanation);

    if (explanation && explanation.term && explanation.content) {
      // Update the existing explanation or add as new one
      const originalId = explanation.original_explanation_id;
      if (originalId) {
        // Try to update the existing explanation
        const updated = explanationManager.updateExplanation(originalId, {
          content: explanation.content,
          timestamp: explanation.timestamp * 1000,
          confidence: typeof explanation.confidence === 'number' ? explanation.confidence : null
        });
        
        if (updated) {
          this._showNotification(`Updated explanation: ${explanation.term}`, 'success');
          console.log(`Renderer: ✅ Updated explanation for "${explanation.term}"`);
          return;
        }
      }
      
      // If update failed or no original ID, add as new explanation
      const confidence = typeof explanation.confidence === 'number' ? explanation.confidence : null;
      explanationManager.addExplanation(
        explanation.term,
        explanation.content,
        explanation.timestamp * 1000,
        confidence
      );

      this._showNotification(`Regenerated explanation: ${explanation.term}`, 'success');
      console.log(`Renderer: ✅ Added regenerated explanation for "${explanation.term}"`);
    } else {
      console.warn('Renderer: ⚠️ Invalid retry explanation data received:', explanation);
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