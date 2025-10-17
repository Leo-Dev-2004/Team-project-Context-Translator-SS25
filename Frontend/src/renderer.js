import { UI } from './components/index.js';
import { explanationManager } from './components/explanation-manager.js';
import { createLoadingMessage, EXPLANATION_CONSTANTS } from './components/explanation-constants.js';
import './components/index.css';
import { Howl } from 'howler';

// --- 1. Preload and cache all sounds for reuse ---
const sounds = {
  launch: new Howl({ src: ['./Sounds/launch_successful.mp3'] }),
  click: new Howl({ src: ['./Sounds/click.mp3'] }),
  join: new Howl({ src: ['./Sounds/join.mp3'] }),
  explanation: new Howl({ src: ['./Sounds/explanation_received.mp3'] }),
  // Sounds not yet implemented are included but won't play
  error: new Howl({ src: [] }),
  notification: new Howl({ src: [] }),
  leave: new Howl({ src: [] }),
  mute: new Howl({ src: [] }),
  unmute: new Howl({ src: [] }),
};

/**
 * Plays a pre-loaded sound from the cache.
 * @param {string} name The name of the sound to play (e.g., 'launch', 'click').
 */
function playSound(name) {
  if (sounds[name] && sounds[name].state() === 'loaded') {
    sounds[name].play();
  } else if (!sounds[name]) {
    console.warn(`Sound "${name}" not found.`);
  }
}

class ElectronMyElement extends UI {
  constructor() {
    super();
    this.platform = 'electron';
    this.isElectron = true;
    this.backendWs = null;
    this.activeNotifications = new Set(); // Track active notifications
    this.maxNotifications = 3; // Limit concurrent notifications
    this.notificationContainer = null; // Container for notifications
    this.messageQueue = []; // Queue for processing messages
    this.isProcessingMessages = false; // Flag to prevent concurrent processing
    this.lastExplanationTime = 0; // Throttle explanations
    this.explanationThrottleMs = 1000; // Minimum time between explanation notifications
    this.notificationCleanupTimeouts = new Set();
    this.audioStream = null;
    console.log('Renderer: ⚙️ ElectronMyElement constructor called.');
  }

  // ### Lifecycle & UI Setup ###

  async firstUpdated(changedProperties) {
    super.firstUpdated(changedProperties); // Call super.firstUpdated first
    this._setupNotificationContainer(); // Set up the notification area
    this._attachActionListeners();
  }

  _setupNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    container.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 1001;
      display: flex;
      flex-direction: column-reverse;
      gap: 10px;
      align-items: center;
      pointer-events: none; /* Allow clicks to pass through */
    `;
    this.shadowRoot.appendChild(container);
    this.notificationContainer = container;
  }

  async connectedCallback() {
    super.connectedCallback();
    console.log('Renderer: ⚙️ connectedCallback entered.');
    await this._initializeElectron();
    this._initializeWebSocket();
    this._initializeMicrophone();
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.backendWs) {
      this.backendWs.close();
      this.backendWs = null;
    }
    this.messageQueue = [];
    this.isProcessingMessages = false;
    this.activeNotifications.forEach(notification => {
      if (notification.parentNode) {
        notification.remove();
      }
    });
    this.activeNotifications.clear();
    this.notificationCleanupTimeouts.forEach(timeoutId => clearTimeout(timeoutId));
    this.notificationCleanupTimeouts.clear();
    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
    }
    playSound('leave');
    console.log('Renderer: ⚙️ disconnectedCallback: All resources cleaned up.');
  }

  async _initializeMicrophone() {
    console.log('Renderer: 🎤 Try to get access to the microphone...');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      this.audioStream = stream;
      const audioTrack = stream.getAudioTracks()[0];
      if (!audioTrack) {
        this.updateMicrophoneStatus('trouble');
        return;
      }
      audioTrack.onmute = () => {
        console.log('Renderer: 🎤 Microphone is muted.');
        this.updateMicrophoneStatus('muted');
        playSound('mute');
      };
      audioTrack.onunmute = () => {
        console.log('Renderer: 🎤 Microphone is unmuted.');
        this.updateMicrophoneStatus('connected');
        playSound('unmute');
      };
      this.updateMicrophoneStatus(audioTrack.muted ? 'muted' : 'connected');
    } catch (error) {
      console.error('Renderer: ❌ Error with microphone access:', error.name, error.message);
      let status = 'trouble';
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        status = 'denied';
      } else if (error.name === 'NotFoundError') {
        status = 'not-found';
      }
      this.updateMicrophoneStatus(status);
      playSound('error');
    }
  }

  _attachActionListeners() {
    this.shadowRoot.addEventListener('click', (event) => {
      const startButton = event.target.closest('#start-session-button');
      const joinButton = event.target.closest('#join-session-button');
      if (startButton) {
        playSound('click');
        this._startSession();
      } else if (joinButton) {
        playSound('join');
        this._joinSession();
      }
    });
  }

  updateServerStatus(newStatus) {
    this.serverStatus = newStatus;
    console.log(`Renderer: 📡 Server-Status updated to: "${newStatus}".`);
  }

  updateMicrophoneStatus(newStatus) {
    this.microphoneStatus = newStatus;
    console.log(`Renderer: 🎤 Microphone-Status updated to: "${newStatus}".`);
  }

  // ### WebSocket & Messaging ###

  // --- 2. Optimized message processing loop ---
  _processMessageQueue() {
    if (this.isProcessingMessages || this.messageQueue.length === 0) {
      return;
    }
    this.isProcessingMessages = true;
    const batchSize = 5; // Process more messages per chunk

    const processLoop = async () => {
      try {
        while (this.messageQueue.length > 0) {
          // Process a batch of messages without blocking the event loop
          const messages = this.messageQueue.splice(0, batchSize);
          for (const message of messages) {
            try {
              console.log(`Renderer: 💡 Processing message from backend:`, message);
              // Await the handler, but the handler itself is now non-blocking
              await this._handleMessage(message);
            } catch (error) {
              console.error('Renderer: ❌ Error processing message:', error);
            }
          }
          // Yield to the browser after the batch to allow for rendering and user input
          await new Promise(resolve => setTimeout(resolve, 16));
        }
      } catch (error) {
        console.error('Renderer: ❌ Error in message processing loop:', error);
      } finally {
        this.isProcessingMessages = false;
      }
    };
    processLoop();
  }
  
  // --- 3. Removed blocking `await updateComplete` calls ---
  async _handleMessage(message) {
    if (message.type === 'session.created') {
      const code = message.payload.code;
      this.sessionCode = code;

      // Defer DOM manipulation without awaiting component updates.
      // This allows Lit to batch the updates asynchronously.
      const setupTab = this.shadowRoot.querySelector('setup-tab');
      if (setupTab) {
        const sessionCodeInput = setupTab.shadowRoot.querySelector('#session-code-input');
        if (sessionCodeInput) {
          sessionCodeInput.value = code;
        }
      }
      const mainBody = this.shadowRoot.querySelector('main-body');
      if (mainBody) {
        const dialog = mainBody.shadowRoot.querySelector('#session-dialog');
        if (dialog) {
          dialog.show();
        }
      }
    } else if (message.type === 'session.joined') {
      this._showNotification(`Successfully joined session ${message.payload.code}`, 'success');
    } else if (message.type === 'session.error') {
      this._showNotification(message.payload.error, 'error');
    } else if (message.type === 'detection.immediate') {
      this._handleImmediateDetection(message.payload);
    } else if (message.type === 'explanation.update') {
      this._handleExplanationUpdate(message.payload);
    } else if (message.type === 'explanation.new') {
      this._handleNewExplanation(message.payload.explanation);
    } else if (message.type === 'explanation.retry') {
      this._handleRetryExplanation(message.payload.explanation);
    }
  }

  _initializeWebSocket() {
    const clientId = `frontend_renderer_${crypto.randomUUID()}`;
    const wsUrl = `ws://localhost:8000/ws/${clientId}`;
    if (this.backendWs) this.backendWs.close();
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = () => {
      console.log(`Renderer: ✅ WebSocket connection established`);
      this.updateServerStatus('connected');
      this._performHandshake();
      playSound('launch');
    };

    this.backendWs.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'system.queue_status_update') return;
        this.messageQueue.push(message);
        this._processMessageQueue();
      } catch (error) {
        console.error('Renderer: ❌ Failed to parse message from backend:', error, event.data);
      }
    };

    this.backendWs.onerror = (error) => {
      console.error(`Renderer: ❌ WebSocket error occurred:`, error);
      this.updateServerStatus('trouble');
      this._showNotification('WebSocket connection failed', 'error');
      playSound('error');
    };
    this.backendWs.onclose = (event) => {
      this.updateServerStatus('disconnected');
      console.warn(`Renderer: 🔌 WebSocket connection closed. Clean: ${event.wasClean}, Code: ${event.code}`);
      playSound('leave');
    };
  }

  async _performHandshake() {
    if (!window.electronAPI) {
      console.error("Renderer: ❌ Electron API not available for handshake.");
      playSound('error');
      return;
    }
    const userSessionId = await window.electronAPI.getUserSessionId();
    this.userSessionId = userSessionId;
    if (!userSessionId) {
      console.warn("Renderer: ⚠️ Could not retrieve User Session ID for handshake.");
      playSound('error');
      return;
    }
    const message = {
      id: crypto.randomUUID(),
      type: 'frontend.init',
      timestamp: Date.now() / 1000,
      payload: { user_session_id: userSessionId }
    };
    this.backendWs.send(JSON.stringify(message));
  }
  
  // ### Other methods remain largely the same, but now call the new `playSound` ###

  _sendManualRequest() {
    const termInput = this.shadowRoot.querySelector('#manual-term-input');
    const term = (termInput?.value || this.manualTerm || '').trim();
    if (!term) return this._showNotification('Please enter a term to explain', 'error');
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) return this._showNotification('No connection to backend', 'error');
    const message = {
      id: crypto.randomUUID(),
      type: 'manual.request',
      timestamp: Date.now() / 1000,
      payload: { term, context: term, domain: this.domainValue || '', explanation_style: this.explanationStyle || 'detailed', user_session_id: this.userSessionId || null },
    };
    try {
      explanationManager.addExplanation(term, 'Generating explanation...', Date.now(), null, true, message.id);
      this.backendWs.send(JSON.stringify(message));
      this._showNotification(`Requested explanation for "${term}"`, 'success');
      if (termInput) termInput.value = '';
      this.manualTerm = '';
      this.requestUpdate?.();
    } catch (e) {
      this._showNotification('Failed to send manual request', 'error');
    }
  }
  
  _startSession() {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) return this._showNotification('No connection to backend', 'error');
    const message = { id: crypto.randomUUID(), type: 'session.start', timestamp: Date.now() / 1000, payload: {} };
    this.backendWs.send(JSON.stringify(message));
  }

  _joinSession(sessionCode) {
    const code = sessionCode ? sessionCode.trim() : '';
    if (!code) return this._showNotification('Please enter a session code', 'error');
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) return this._showNotification('No connection to backend', 'error');
    const message = { id: crypto.randomUUID(), type: 'session.join', timestamp: Date.now() / 1000, payload: { code: code } };
    this.backendWs.send(JSON.stringify(message));
  }

  async _initializeElectron() {
    if (window.electronAPI) {
      try {
        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings) this._loadSettingsFromElectron(result.settings);
      } catch (error) {
        console.error('Renderer: ❌ Error during Electron initialization:', error);
      }
    }
  }

  _loadSettingsFromElectron(settings) {
    if (settings.domain) this.domainValue = settings.domain;
    if (settings.explanationStyle) this.explanationStyle = settings.explanationStyle;
  }

  async _saveSettings() {
    if (!window.electronAPI) return console.error("Renderer: ❌ window.electronAPI not available.");
    const settings = { domain: this.domainValue, explanationStyle: this.explanationStyle };
    try {
      const result = await window.electronAPI.saveSettings(settings);
      if (result.success) {
        this._showNotification('Settings saved successfully', 'success');
      } else {
        this._showNotification('Failed to save settings', 'error');
      }
      if (this.backendWs && this.backendWs.readyState === WebSocket.OPEN) {
        const message = { id: crypto.randomUUID(), type: 'settings.save', timestamp: Date.now() / 1000, payload: { domain: this.domainValue || '', explanation_style: this.explanationStyle || 'detailed' } };
        this.backendWs.send(JSON.stringify(message));
      }
    } catch (error) {
      console.error('Renderer: ❌ Error saving settings:', error);
      this._showNotification('Error saving settings', 'error');
    }
    if (settings.explanationStyle) this.explanationStyle = settings.explanationStyle;
  }

  _resetSettings() {
    super._resetSettings();
    this._saveSettings();
  }

  _handleRegenerate(explanation) {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) return this._showNotification('No connection to backend', 'error');
    const message = { id: crypto.randomUUID(), type: 'explanation.retry', timestamp: Date.now() / 1000, payload: { original_explanation_id: explanation.id, term: explanation.title, context: explanation.title, user_session_id: this.userSessionId || null, explanation_style: this.explanationStyle } };
    try {
      this.backendWs.send(JSON.stringify(message));
      this._showNotification(`Regenerating explanation for "${explanation.title}"`, 'success');
    } catch (error) {
      this._showNotification('Failed to send regenerate request', 'error');
    }
  }

  _handleNewExplanation(explanation) {
    if (!explanation?.term || !explanation.content) return console.warn('Renderer: ⚠️ Invalid explanation data received:', explanation);
    const existingExplanation = explanationManager.findExplanationToUpdate(explanation.term);
    if (existingExplanation) {
      explanationManager.updateExplanation(existingExplanation.id, { content: explanation.content, timestamp: explanation.timestamp * 1000, confidence: explanation.confidence, isPending: false });
    } else {
      explanationManager.addExplanation(explanation.term, explanation.content, explanation.timestamp * 1000, explanation.confidence);
    }
    const now = Date.now();
    if (now - this.lastExplanationTime >= this.explanationThrottleMs) {
      this._showNotification(`New explanation: ${explanation.term}`, 'success');
      this.lastExplanationTime = now;
    }
  }

  _handleRetryExplanation(explanation) {
    if (!explanation?.term || !explanation.content) return console.warn('Renderer: ⚠️ Invalid retry explanation data received:', explanation);
    if (explanation.original_explanation_id && explanationManager.updateExplanation(explanation.original_explanation_id, { content: explanation.content, timestamp: explanation.timestamp * 1000, confidence: explanation.confidence })) {
      this._showNotification(`Updated explanation: ${explanation.term}`, 'success');
    } else {
      explanationManager.addExplanation(explanation.term, explanation.content, explanation.timestamp * 1000, explanation.confidence);
      this._showNotification(`Regenerated explanation: ${explanation.term}`, 'success');
    }
  }

  _handleImmediateDetection(payload) {
    if (!payload?.detected_terms?.length) return console.warn('Renderer: ⚠️ Invalid immediate detection data received:', payload);
    const termCount = payload.detected_terms.length;
    this._showNotification(`🔍 Detected ${termCount} technical term${termCount > 1 ? 's' : ''}...`, 'info');
    payload.detected_terms.forEach(termData => {
      const existing = explanationManager.explanations.find(exp => exp.title === termData.term && !exp.isDeleted);
      if (!existing) {
        explanationManager.addExplanation(termData.term, createLoadingMessage(termData.term, termData.context), Date.now(), termData.confidence);
      }
    });
    playSound('explanation');
  }

  _handleExplanationUpdate(payload) {
    if (!payload?.term || !payload.explanation) return console.warn('Renderer: ⚠️ Invalid explanation update data received:', payload);
    const existingExplanation = explanationManager.findExplanationToUpdate(payload.term);
    if (existingExplanation) {
      explanationManager.updateExplanation(existingExplanation.id, { content: payload.explanation, timestamp: (payload.timestamp || Date.now() / 1000) * 1000, confidence: payload.confidence, isPending: false });
      this._showNotification(`✨ Explanation ready: ${payload.term}`, 'success');
    } else {
      explanationManager.addExplanation(payload.term, payload.explanation, (payload.timestamp || Date.now() / 1000) * 1000, payload.confidence);
    }
  }

  // --- 4. More efficient notification handling ---
  _showNotification(message, type = 'success') {
    if (!this.notificationContainer) return;

    if (this.activeNotifications.size >= this.maxNotifications) {
      const oldestNotification = this.activeNotifications.values().next().value;
      if (oldestNotification && oldestNotification.parentNode) {
        oldestNotification.remove();
        this.activeNotifications.delete(oldestNotification);
      }
    }

    const notification = document.createElement('div');
    notification.textContent = message;
    // No positional styles needed; the container handles stacking.
    notification.style.cssText = `
      padding: 12px 24px;
      border-radius: 8px;
      color: white;
      font-family: 'Roboto', sans-serif;
      background-color: ${type === 'error' ? '#D32F2F' : type === 'info' ? '#1976D2' : '#2E7D32'};
      box-shadow: 0 4px 8px rgba(0,0,0,0.2);
      transition: all 0.3s ease;
      pointer-events: auto; /* Re-enable pointer events for the notification itself */
    `;
    
    this.notificationContainer.appendChild(notification);
    this.activeNotifications.add(notification);
    
    const timeoutId = setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
      this.activeNotifications.delete(notification);
      this.notificationCleanupTimeouts.delete(timeoutId);
    }, 4000);
    this.notificationCleanupTimeouts.add(timeoutId);
  }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement);
} else {
  console.warn("Renderer: Custom element 'my-element' is already defined.");
}