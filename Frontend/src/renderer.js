import { UI } from './components/index.js';
import { explanationManager } from './components/explanation-manager.js';
import { createLoadingMessage, EXPLANATION_CONSTANTS } from './components/explanation-constants.js';
import './components/index.css';
import { Howl } from 'howler';


const launch_sound = './Sounds/launch_successful.mp3';
const click_sound = './Sounds/click.mp3';
const join_sound = './Sounds/join.mp3';
const explanation_sound = './Sounds/explanation_received.mp3';

const error_sound = 'NOT IMPLEMENTED YET';
const notification_sound = 'NOT IMPLEMENTED YET';
const leave_sound = 'NOT IMPLEMENTED YET';
const mute_sound = 'NOT IMPLEMENTED YET';
const unmute_sound = 'NOT IMPLEMENTED YET';





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
    // play launch sound
    // playSound(launch_sound);   // maybe another first sound for app startup?

    super.firstUpdated(changedProperties); // Call super.firstUpdated first
  // Hauptinitialisierung erfolgt über connectedCallback (Electron/WebSocket)
  // Entfernt: initializeApplication (nicht definiert) und doppelte Electron-Init
  
    // Attach event listeners to action buttons
    this._attachActionListeners();
  }

  // connectedCallback is still useful for handlers, but main app init is in firstUpdated
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
    playSound(leave_sound);
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
      playSound(mute_sound);
    };

    audioTrack.onunmute = () => {
      console.log('Renderer: 🎤 Microphone is unmuted.');
      this.updateMicrophoneStatus('connected');
      playSound(unmute_sound);
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
      playSound(error_sound);
    } else if (error.name === 'NotFoundError') {
      // No microphone found on the system
      console.warn('Renderer: 🎤 No microphone found.');
      this.updateMicrophoneStatus('not-found'); // Clear status for "not found"
      playSound(error_sound);
    } else {
      // Other unexpected errors (e.g. hardware issues)
      console.error('Renderer: 🎤 An unexpected error occurred.');
      this.updateMicrophoneStatus('trouble'); // General error status
      playSound(error_sound);
    }
    }
  }
  
  _attachActionListeners() {
    console.log('Renderer: 💡 Attaching event listeners via delegation...');

    // Hänge EINEN Listener an einen Container, der immer existiert.
    this.shadowRoot.addEventListener('click', (event) => {
        // Finde heraus, ob ein Button geklickt wurde, der uns interessiert.
        // .closest() ist robust, weil es auch funktioniert, wenn du z.B. ein Icon im Button klickst.
        const startButton = event.target.closest('#start-session-button');
        const joinButton = event.target.closest('#join-session-button');

        if (startButton) {
            playSound(click_sound);
            this._startSession();
            return; // Beende die Funktion hier
        }

        if (joinButton) {
            playSound(join_sound);
            this._joinSession();
            return; // Beende die Funktion hier
        }
    });

    console.log('Renderer: ✅ Event delegation successfully attached.');
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
      this.sessionCode = code;
      
      // Wait for the component to update with the new sessionCode
      await this.updateComplete;
      
      // Set the session code in the input field
      const setupTab = this.shadowRoot.querySelector('setup-tab');
      if (setupTab) {
        await setupTab.updateComplete;
        const sessionCodeInput = setupTab.shadowRoot.querySelector('#session-code-input');
        if (sessionCodeInput) {
          sessionCodeInput.value = code;
        }
      }
      
      // Access the dialog through the main-body component
      const mainBody = this.shadowRoot.querySelector('main-body');
      if (mainBody) {
        await mainBody.updateComplete;
        const dialog = mainBody.shadowRoot.querySelector('#session-dialog');
        if (dialog) {
          dialog.show(); // Use .show() for non-modal
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
    console.log(`Renderer: ⚙️ Attempting WebSocket connection to ${wsUrl}...`);

    if (this.backendWs) this.backendWs.close();
    
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = () => {
      console.log(`Renderer: ✅ WebSocket connection established to ${wsUrl}`);
      this.updateServerStatus('connected');
      this._performHandshake();
      playSound(launch_sound);
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
      console.error(`Renderer: ❌ WebSocket error occurred on connection to ${wsUrl}:`, error);
      this.updateServerStatus('trouble');
      this._showNotification('WebSocket connection failed', 'error');
      playSound(error_sound);
    };
    this.backendWs.onclose = (event) => {
      this.updateServerStatus('disconnected');
      const reason = event.reason || 'No reason provided';
      const code = event.code || 'Unknown';
      const wasClean = event.wasClean ? 'cleanly' : 'unexpectedly';
      console.warn(`Renderer: 🔌 WebSocket connection to ${wsUrl} closed ${wasClean}. Code: ${code}, Reason: ${reason}`);
      playSound(leave_sound);
      // Optionally implement reconnection logic here
    };
  }

  async _performHandshake() {
    if (!window.electronAPI) {
        console.error("Renderer: ❌ Electron API not available for handshake.");
        playSound(error_sound);
        return;
    }
    const userSessionId = await window.electronAPI.getUserSessionId();
    this.userSessionId = userSessionId;
    
    if (!userSessionId) {
        console.warn("Renderer: ⚠️ Could not retrieve User Session ID for handshake.");
        playSound(error_sound);
        return;
    }

    console.log(`Renderer: 🚀 Sending "frontend.init" with User Session ID: ${userSessionId}`);
    const message = {
      id: crypto.randomUUID(),
      type: 'frontend.init',
      timestamp: Date.now() / 1000,
      payload: { user_session_id: userSessionId }
    };
    this.backendWs.send(JSON.stringify(message));
    console.log(`Renderer: 📤 Sent handshake init message for session ${userSessionId}`);
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
      // Immediately add a pending explanation to the UI
      const pendingExplanation = explanationManager.addExplanation(
        term,
        'Generating explanation...', // Placeholder content
        Date.now(),
        null, // No confidence yet
        true, // isPending = true
        message.id // Use message ID as request ID to match responses
      );

      this.backendWs.send(JSON.stringify(message));
      this._showNotification(`Requested explanation for "${term}"`, 'success');
      // Clear field in UI
      if (termInput) termInput.value = '';
      this.manualTerm = '';
      this.requestUpdate?.();
      
      console.log(`Renderer: ✅ Added pending explanation for "${term}" with ID ${pendingExplanation.id}`);
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

  _joinSession(sessionCode) {
    const code = sessionCode ? sessionCode.trim() : '';

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
      return console.error("Renderer: ❌ window.electronAPI not available for saving settings.");
    }

    const settings = {
      domain: this.domainValue,
      explanationStyle: this.explanationStyle
    };

    console.log('Renderer: 💾 Starting settings save process with:', settings);

    try {
      // Save settings locally via Electron IPC
      const ipcStartTime = Date.now();
      console.log('Renderer: 📤 Calling Electron IPC saveSettings...');
      const result = await window.electronAPI.saveSettings(settings);
      const ipcDuration = Date.now() - ipcStartTime;
      
      if (result.success) {
        console.log(`Renderer: ✅ IPC saveSettings completed successfully (${ipcDuration}ms)`);
        this._showNotification('Settings saved successfully', 'success');
      } else {
        console.error('Renderer: ❌ IPC saveSettings failed:', result.error);
        this._showNotification('Failed to save settings', 'error');
      }
      
      // Also send settings to Backend via WebSocket for global settings management
      if (this.backendWs && this.backendWs.readyState === WebSocket.OPEN) {
        const message = {
          id: crypto.randomUUID(),
          type: 'settings.save',
          timestamp: Date.now() / 1000,
          payload: {
            domain: this.domainValue || '',
            explanation_style: this.explanationStyle || 'detailed'
          },
          client_id: this.userSessionId || `frontend_renderer_${crypto.randomUUID()}`,
          origin: 'Frontend',
          destination: 'Backend'
        };
        
        try {
          console.log('Renderer: 📡 Sending settings to Backend via WebSocket (message ID:', message.id + ')...');
          this.backendWs.send(JSON.stringify(message));
          console.log('Renderer: ✅ Settings sent to Backend via WebSocket:', message.payload);
        } catch (wsError) {
          console.error('Renderer: ❌ Failed to send settings to Backend via WebSocket:', wsError);
          // Don't show error to user as local save succeeded
        }
      } else {
        console.log('Renderer: ⚠️ Backend WebSocket not available, settings only saved locally');
      }
      
    } catch (error) {
      console.error('Renderer: ❌ Error saving settings:', error);
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
      // First, check if there's already an explanation with this term that needs updating
      // (pending manual requests, automatic detections, or explanations with missing/default content)
      const existingExplanation = explanationManager.findExplanationToUpdate(explanation.term);
      
      if (existingExplanation) {
        console.log(`Renderer: 🔄 Found existing explanation to update for "${explanation.term}"`);
        
        // Update the existing explanation instead of creating a new one
        const updated = explanationManager.updateExplanation(existingExplanation.id, {
          content: explanation.content,
          timestamp: explanation.timestamp * 1000, // Convert to milliseconds if needed
          confidence: typeof explanation.confidence === 'number' ? explanation.confidence : null,
          isPending: false // Mark as no longer pending
        });

        if (updated) {
          console.log(`Renderer: ✅ Updated existing explanation for "${explanation.term}"`);
          
          // Throttle notification display to prevent notification spam
          const now = Date.now();
          if (now - this.lastExplanationTime >= this.explanationThrottleMs) {
            this._showNotification(`Explanation ready: ${explanation.term}`, 'success');
            this.lastExplanationTime = now;
          }
          return;
        }
      }

      // If no existing explanation found or update failed, check for recent explanations to prevent race condition duplicates
      const existingExplanations = explanationManager.explanations;
      const recentExplanation = existingExplanations.find(exp => 
        exp.title === explanation.term && 
        !exp.isDeleted &&
        exp.content && 
        exp.content !== 'Generating explanation...' &&
        !exp.content.includes('🔄 Generating explanation') &&
        (Date.now() - exp.createdAt) < 5000 // Created within last 5 seconds
      );

      if (recentExplanation) {
        console.log(`Renderer: 🛡️ Skipping duplicate explanation.new for "${explanation.term}" - recent explanation exists`);
        return;
      }

      // Final fallback: Add as completely new explanation
      const confidence = typeof explanation.confidence === 'number' ? explanation.confidence : null;
      explanationManager.addExplanation(
        explanation.term,
        explanation.content,
        explanation.timestamp * 1000, // Convert to milliseconds if needed
        confidence
      );
      console.log(`Renderer: ✅ Added new explanation for "${explanation.term}"`);

      // Throttle notification display to prevent notification spam
      const now = Date.now();
      if (now - this.lastExplanationTime >= this.explanationThrottleMs) {
        this._showNotification(`New explanation: ${explanation.term}`, 'success');
        this.lastExplanationTime = now;
      }
    } else {
      console.warn('Renderer: ⚠️ Invalid explanation data received:', explanation);
    }
  }

  _handleRetryExplanation(explanation) {
    console.log(`Renderer: ${EXPLANATION_CONSTANTS.GENERATING_EMOJI} Retry explanation received:`, explanation);

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

  _handleImmediateDetection(payload) {
    console.log('Renderer: ⚡ Immediate detection received:', payload);

    if (payload && payload.detected_terms && Array.isArray(payload.detected_terms)) {
      const termCount = payload.detected_terms.length;
      
      // Show immediate feedback to user
      this._showNotification(`🔍 Detected ${termCount} technical term${termCount > 1 ? 's' : ''} - generating explanations...`, 'info');

      // Add placeholders for detected terms (without full explanations yet)
      payload.detected_terms.forEach(termData => {
        if (termData.term && termData.context) {
          // Check if we already have an explanation for this term (including pending manual requests)
          const existingExplanations = explanationManager.explanations;
          const existingIndex = existingExplanations.findIndex(exp => 
            exp.title === termData.term && !exp.isDeleted
          );

          if (existingIndex !== -1) {
            console.log(`Renderer: ⚡ Skipping detection placeholder for "${termData.term}" - explanation already exists`);
            return; // Skip adding duplicate
          }

          const confidence = typeof termData.confidence === 'number' ? termData.confidence : null;
          
          // Add as placeholder with loading state
          explanationManager.addExplanation(
            termData.term,
            createLoadingMessage(termData.term, termData.context),
            Date.now(),
            confidence
          );
          
          console.log(`Renderer: ⚡ Added detection placeholder for "${termData.term}"`);
        }
      });
      
      // Play detection sound for immediate feedback
      playSound(explanation_sound);
    } else {
      console.warn('Renderer: ⚠️ Invalid immediate detection data received:', payload);
    }
  }

  _handleExplanationUpdate(payload) {
    console.log('Renderer: 📝 Explanation update received:', payload);

    if (payload && payload.term && payload.explanation) {
      // First, check if there's already an explanation with this term that needs updating
      // (pending manual requests, automatic detections, or explanations with missing/default content)
      const existingExplanation = explanationManager.findExplanationToUpdate(payload.term);
      
      if (existingExplanation) {
        console.log(`Renderer: 🔄 Found existing explanation to update for "${payload.term}"`);
        
        // Update the existing explanation instead of creating a new one
        const updated = explanationManager.updateExplanation(existingExplanation.id, {
          content: payload.explanation,
          timestamp: (payload.timestamp || Date.now() / 1000) * 1000,
          confidence: typeof payload.confidence === 'number' ? payload.confidence : null,
          isPending: false // Mark as no longer pending
        });

        if (updated) {
          console.log(`Renderer: ✅ Updated existing explanation for "${payload.term}" via explanation.update`);
          this._showNotification(`✨ Explanation ready: ${payload.term}`, 'success');
          return;
        }
      }

      // If no existing explanation found or update failed, check for recent explanations to prevent race condition duplicates
      const existingExplanations = explanationManager.explanations;
      const recentExplanation = existingExplanations.find(exp => 
        exp.title === payload.term && 
        !exp.isDeleted &&
        exp.content && 
        exp.content !== 'Generating explanation...' &&
        !exp.content.includes('🔄 Generating explanation') &&
        (Date.now() - exp.createdAt) < 5000 // Created within last 5 seconds
      );

      if (recentExplanation) {
        console.log(`Renderer: 🛡️ Skipped duplicate explanation.update for "${payload.term}" - recent explanation exists`);
        return;
      }

      // Final fallback: Add as new explanation
      const confidence = typeof payload.confidence === 'number' ? payload.confidence : null;
      explanationManager.addExplanation(
        payload.term,
        payload.explanation,
        (payload.timestamp || Date.now() / 1000) * 1000,
        confidence
      );
      console.log(`Renderer: ✅ Added new explanation for "${payload.term}" via explanation.update`);
    } else {
      console.warn('Renderer: ⚠️ Invalid explanation update data received:', payload);
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
      background-color: ${type === 'error' ? '#D32F2F' : type === 'info' ? '#1976D2' : '#2E7D32'};
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

function playSound(path) {
  const launchSound = new Howl({
    src: [path] // The path is relative to the `index.html` file
  });
  launchSound.play();
}