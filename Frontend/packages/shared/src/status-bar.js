/**
 * Status Bar Component Module - Real-time Application Status Display
 * 
 * A comprehensive status bar component for the Team Project Context Translator application.
 * Provides real-time monitoring of WebSocket connections, service health, and system status
 * with an extensible architecture for future status sources.
 * 
 * @extends LitElement
 */

// Import Lit framework core components for web component creation
import { LitElement, html, css } from 'lit';

// Import shared styling configurations for consistent theming across components
import { sharedStyles } from './styles.js';

/**
 * StatusBar Web Component
 * 
 * A comprehensive status display component that provides real-time monitoring
 * of application connection states, service health, and WebSocket controls.
 * Implements a modular architecture for flexible status source integration.
 * 
 * @extends LitElement
 */
export class StatusBar extends LitElement {
  /**
   * Reactive properties that trigger re-rendering when changed
   */
  static properties = {
    connectionStatus: { type: String },
    isConnecting: { type: Boolean },
    showDetails: { type: Boolean },
    microStatus: { type: String },
    lastHeartbeat: { type: Number },
    clientId: { type: String },
    reconnectAttempts: { type: Number }
  };

  /**
   * Component Styles
   */
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        width: 100%;
        margin: 0.5rem 0;
      }

      .status-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1rem;
        background: var(--md-sys-color-surface-container-low, #f5f5f5);
        border: 1px solid var(--md-sys-color-outline-variant, #ddd);
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
      }

      .status-bar:hover {
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
      }

      .status-section {
        display: flex;
        align-items: center;
        gap: 0.75rem;
      }

      .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.5rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        transition: all 0.2s ease;
      }

      .status-indicator.connected {
        background: #d1fae5;
        color: #059669;
      }

      .status-indicator.connecting {
        background: #fef3c7;
        color: #d97706;
      }

      .status-indicator.disconnected {
        background: #fee2e2;
        color: #dc2626;
      }

      .status-indicator.error {
        background: #fecaca;
        color: #b91c1c;
      }

      .status-dot {
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 50%;
        background: currentColor;
      }

      .status-dot.pulse {
        animation: pulse 2s infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.1); }
      }

      .micro-status {
        font-size: 0.75rem;
        color: var(--md-sys-color-on-surface-variant, #666);
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        background: var(--md-sys-color-surface-variant, #f0f0f0);
      }

      .controls {
        display: flex;
        gap: 0.5rem;
        align-items: center;
      }

      .details-toggle {
        background: none;
        border: 1px solid var(--md-sys-color-outline, #ccc);
        border-radius: 0.25rem;
        padding: 0.25rem;
        cursor: pointer;
        display: flex;
        align-items: center;
        color: var(--md-sys-color-on-surface, #333);
      }

      .details-toggle:hover {
        background: var(--md-sys-color-surface-variant, #f5f5f5);
      }

      .details-section {
        margin-top: 0.75rem;
        padding: 0.75rem;
        background: var(--md-sys-color-surface-container-lowest, #fafafa);
        border-radius: 0.375rem;
        border: 1px solid var(--md-sys-color-outline-variant, #ddd);
      }

      .details-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 0.75rem;
      }

      .detail-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem;
        background: var(--md-sys-color-surface, #fff);
        border-radius: 0.25rem;
        font-size: 0.875rem;
        border: 1px solid var(--md-sys-color-outline-variant, #eee);
      }

      .detail-label {
        color: var(--md-sys-color-on-surface-variant, #666);
        font-weight: 500;
      }

      .detail-value {
        color: var(--md-sys-color-on-surface, #333);
        font-family: monospace;
        font-size: 0.8rem;
      }

      button {
        padding: 0.5rem 1rem;
        border: 1px solid var(--md-sys-color-outline, #ccc);
        border-radius: 0.25rem;
        background: var(--md-sys-color-surface, #fff);
        cursor: pointer;
        font-size: 0.875rem;
        transition: all 0.2s ease;
      }

      button:hover:not(:disabled) {
        background: var(--md-sys-color-surface-variant, #f5f5f5);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .connect-btn {
        background: var(--md-sys-color-primary, #0066cc);
        color: var(--md-sys-color-on-primary, #fff);
        border-color: var(--md-sys-color-primary, #0066cc);
      }

      .connect-btn:hover:not(:disabled) {
        background: var(--md-sys-color-primary-container, #004494);
      }

      .disconnect-btn {
        background: var(--md-sys-color-error, #dc2626);
        color: var(--md-sys-color-on-error, #fff);
        border-color: var(--md-sys-color-error, #dc2626);
      }

      .disconnect-btn:hover:not(:disabled) {
        background: var(--md-sys-color-error-container, #b91c1c);
      }

      @media (max-width: 768px) {
        .status-bar {
          flex-direction: column;
          align-items: stretch;
          gap: 0.5rem;
        }

        .status-section {
          justify-content: space-between;
        }

        .details-grid {
          grid-template-columns: 1fr;
        }
      }
    `
  ];

  /**
   * Component Constructor
   */
  constructor() {
    super();
    this.connectionStatus = 'disconnected';
    this.isConnecting = false;
    this.showDetails = false;
    this.microStatus = 'unknown';
    this.lastHeartbeat = 0;
    this.clientId = '';
    this.reconnectAttempts = 0;
  }

  /**
   * Lifecycle method - setup when component is added to DOM
   */
  connectedCallback() {
    super.connectedCallback();
    this._setupStatusMonitoring();
  }

  /**
   * Lifecycle method - cleanup when component is removed from DOM
   */
  disconnectedCallback() {
    super.disconnectedCallback();
    this._cleanupStatusMonitoring();
  }

  /**
   * Setup status monitoring system
   * @private
   */
  _setupStatusMonitoring() {
    // Check WebSocket status every second
    this._statusInterval = setInterval(() => {
      this._updateStatus();
    }, 1000);

    // Check for existing WebSocketManager
    this._checkWebSocketManager();
  }

  /**
   * Check for WebSocketManager availability
   * @private
   */
  _checkWebSocketManager() {
    if (window.WebSocketManager) {
      // Get current status
      this._updateFromWebSocketManager();
      
      // Set up more frequent checks for WebSocket state
      this._wsCheckInterval = setInterval(() => {
        this._updateFromWebSocketManager();
      }, 500);
    }
  }

  /**
   * Update status from WebSocketManager
   * @private
   */
  _updateFromWebSocketManager() {
    if (!window.WebSocketManager) return;

    const wsManager = window.WebSocketManager;
    
    // Update connection status based on WebSocket state
    if (wsManager.isConnected && wsManager.isConnected()) {
      if (this.connectionStatus !== 'connected') {
        this.connectionStatus = 'connected';
        this.lastHeartbeat = Date.now();
        this.isConnecting = false;
      }
    } else if (wsManager.ws) {
      // Check WebSocket ready state
      switch (wsManager.ws.readyState) {
        case WebSocket.CONNECTING:
          this.connectionStatus = 'connecting';
          this.isConnecting = true;
          break;
        case WebSocket.OPEN:
          this.connectionStatus = 'connected';
          this.lastHeartbeat = Date.now();
          this.isConnecting = false;
          break;
        case WebSocket.CLOSING:
          this.connectionStatus = 'disconnected';
          this.isConnecting = false;
          break;
        case WebSocket.CLOSED:
          this.connectionStatus = 'disconnected';
          this.isConnecting = false;
          break;
        default:
          this.connectionStatus = 'disconnected';
          this.isConnecting = false;
      }
    } else {
      this.connectionStatus = 'disconnected';
      this.isConnecting = false;
    }

    // Update client ID
    if (wsManager.clientId) {
      this.clientId = wsManager.clientId;
    }
  }

  /**
   * Update general status
   * @private
   */
  _updateStatus() {
    // Update microphone status (placeholder)
    this._updateMicrophoneStatus();
    
    // Update from WebSocket if available
    if (window.WebSocketManager) {
      this._updateFromWebSocketManager();
    }
  }

  /**
   * Update microphone status
   * @private
   */
  _updateMicrophoneStatus() {
    // Check if we have microphone permissions
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.permissions.query({ name: 'microphone' }).then((result) => {
        switch (result.state) {
          case 'granted':
            this.microStatus = 'available';
            break;
          case 'denied':
            this.microStatus = 'denied';
            break;
          case 'prompt':
            this.microStatus = 'prompt';
            break;
          default:
            this.microStatus = 'unknown';
        }
      }).catch(() => {
        this.microStatus = 'unknown';
      });
    } else {
      this.microStatus = 'unavailable';
    }
  }

  /**
   * Cleanup status monitoring
   * @private
   */
  _cleanupStatusMonitoring() {
    if (this._statusInterval) {
      clearInterval(this._statusInterval);
    }
    if (this._wsCheckInterval) {
      clearInterval(this._wsCheckInterval);
    }
  }

  /**
   * Handle connect button click
   */
  async _handleConnect() {
    if (this.isConnecting || this.connectionStatus === 'connected') {
      return;
    }

    try {
      this.isConnecting = true;
      this.connectionStatus = 'connecting';

      if (window.WebSocketManager) {
        // Use actual WebSocketManager
        await window.WebSocketManager.connect();
      } else {
        // Fallback simulation for testing
        await new Promise(resolve => setTimeout(resolve, 2000));
        this.connectionStatus = 'connected';
        this.lastHeartbeat = Date.now();
      }
    } catch (error) {
      console.error('StatusBar: Failed to connect:', error);
      this.connectionStatus = 'error';
      this._showError('Connection failed: ' + error.message);
    } finally {
      this.isConnecting = false;
    }
  }

  /**
   * Handle disconnect button click
   */
  async _handleDisconnect() {
    try {
      if (window.WebSocketManager && window.WebSocketManager.ws) {
        window.WebSocketManager.ws.close();
      }
      
      this.connectionStatus = 'disconnected';
      this.isConnecting = false;
    } catch (error) {
      console.error('StatusBar: Failed to disconnect:', error);
    }
  }

  /**
   * Toggle details view
   */
  _toggleDetails() {
    this.showDetails = !this.showDetails;
  }

  /**
   * Show error message
   * @param {string} message - Error message
   * @private
   */
  _showError(message) {
    console.error('StatusBar Error:', message);
    // Could integrate with notification system here
  }

  /**
   * Get status label
   */
  _getStatusLabel() {
    switch (this.connectionStatus) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'disconnected': return 'Disconnected';
      case 'error': return 'Connection Error';
      default: return 'Unknown';
    }
  }

  /**
   * Get microphone status label
   */
  _getMicroLabel() {
    switch (this.microStatus) {
      case 'available': return 'Ready';
      case 'denied': return 'Denied';
      case 'prompt': return 'Needs Permission';
      case 'unavailable': return 'Unavailable';
      default: return 'Unknown';
    }
  }

  /**
   * Format timestamp
   * @param {number} timestamp - Unix timestamp
   */
  _formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleTimeString();
  }

  /**
   * Render status indicator
   * @private
   */
  _renderStatusIndicator() {
    const statusClass = this.connectionStatus.toLowerCase();
    const shouldPulse = this.connectionStatus === 'connecting';
    
    return html`
      <div class="status-indicator ${statusClass}">
        <div class="status-dot ${shouldPulse ? 'pulse' : ''}"></div>
        <span>${this._getStatusLabel()}</span>
      </div>
    `;
  }

  /**
   * Render control buttons
   * @private
   */
  _renderControls() {
    const isConnected = this.connectionStatus === 'connected';
    const isConnecting = this.isConnecting || this.connectionStatus === 'connecting';
    
    return html`
      <div class="controls">
        ${!isConnected ? html`
          <button 
            class="connect-btn"
            @click=${this._handleConnect} 
            ?disabled=${isConnecting}
          >
            ${isConnecting ? 'Connecting...' : 'Connect'}
          </button>
        ` : html`
          <button 
            class="disconnect-btn"
            @click=${this._handleDisconnect}
          >
            Disconnect
          </button>
        `}
        
        <button class="details-toggle" @click=${this._toggleDetails} title="Toggle details">
          <span>${this.showDetails ? '▲' : '▼'}</span>
        </button>
      </div>
    `;
  }

  /**
   * Render detailed status information
   * @private
   */
  _renderDetails() {
    if (!this.showDetails) return '';
    
    return html`
      <div class="details-section">
        <div class="details-grid">
          <div class="detail-item">
            <span class="detail-label">Connection:</span>
            <span class="detail-value">${this.connectionStatus}</span>
          </div>
          
          <div class="detail-item">
            <span class="detail-label">Last Heartbeat:</span>
            <span class="detail-value">${this._formatTimestamp(this.lastHeartbeat)}</span>
          </div>
          
          <div class="detail-item">
            <span class="detail-label">Microphone:</span>
            <span class="detail-value">${this._getMicroLabel()}</span>
          </div>
          
          <div class="detail-item">
            <span class="detail-label">Client ID:</span>
            <span class="detail-value">${this.clientId || 'Not set'}</span>
          </div>
          
          <div class="detail-item">
            <span class="detail-label">WebSocket Manager:</span>
            <span class="detail-value">${window.WebSocketManager ? 'Available' : 'Not loaded'}</span>
          </div>
          
          <div class="detail-item">
            <span class="detail-label">Reconnect Attempts:</span>
            <span class="detail-value">${this.reconnectAttempts}</span>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Main render method
   */
  render() {
    return html`
      <div class="status-bar">
        <div class="status-section">
          ${this._renderStatusIndicator()}
          <div class="micro-status">
            Mic: ${this._getMicroLabel()}
          </div>
        </div>
        
        ${this._renderControls()}
      </div>
      
      ${this._renderDetails()}
    `;
  }
}

/**
 * Custom Element Registration
 */
customElements.define('status-bar', StatusBar);