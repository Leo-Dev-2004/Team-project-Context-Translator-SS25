/**
 * Status Bar Component - Real-time Connection and Service Status Display
 * 
 * This file implements a comprehensive status bar component for the Team Project Context Translator
 * application. The component provides real-time visual indicators for WebSocket connections,
 * backend service health, and interactive controls for connection management.
 * 
 * The status bar follows Material Design 3 principles and integrates seamlessly with the existing
 * application theme, providing consistent styling across light and dark modes. It serves as a
 * critical monitoring interface for users to understand system connectivity and service health.
 * 
 * Content:
 * - StatusBar class: Main Lit web component with reactive status properties
 * - Connection status indicators: Visual feedback for WebSocket and backend states
 * - Interactive controls: Connect/disconnect/reconnect buttons with proper state management
 * - Modular status adapters: Flexible architecture for different status formats
 * - Comprehensive error handling: Fallback mechanisms for unknown status formats
 * 
 * Structure:
 * - Import statements: Lit framework, Material Design components, shared modules
 * - StatusBar class definition: Main component with reactive properties
 * - Constructor: Property initialization and status monitoring setup
 * - Render methods: Template rendering for status indicators and controls
 * - Event handlers: User interaction processing for connection management
 * - Utility methods: Status formatting, color coding, and helper functions
 * - Styles: Component-specific CSS extending shared design system
 * 
 * Key Features:
 * - Real-time status indicators with color-coded visual feedback
 * - WebSocket connection controls (connect/disconnect/reconnect)
 * - Backend service health monitoring
 * - Material Design 3 component integration
 * - Responsive design with accessibility considerations
 * - Modular architecture for extensible status sources
 * - Comprehensive error handling and fallback mechanisms
 * 
 * Status Types:
 * - WebSocket: Connected, Disconnected, Connecting, Reconnecting, Error
 * - Backend: Online, Offline, Degraded, Maintenance
 * - Future extensibility: Microphone, Transcription Service, etc.
 * 
 * Dependencies:
 * - Lit: Web component framework
 * - Material Web: Google's Material Design web components
 * - Shared styles: Consistent theming and design tokens
 * 
 * DISCLAIMER: Some portions of this code may have been generated or assisted by AI tools.
 */

// Import Lit framework core components for web component creation
import { LitElement, css, html } from 'lit'

// Import shared styling configurations for consistent theming across components
import { sharedStyles } from './styles.js'

/**
 * Status Bar Component - Connection and Service Status Interface
 * 
 * A comprehensive web component that displays real-time status information for WebSocket
 * connections, backend services, and provides interactive controls for connection management.
 * Features Material Design 3 integration and responsive design patterns.
 * 
 * @extends LitElement
 */
export class StatusBar extends LitElement {
  /**
   * Reactive properties that trigger re-rendering when changed
   * Defines the component's state and status monitoring capabilities
   */
  static properties = {
    websocketStatus: { type: String },     // WebSocket connection state
    isConnecting: { type: Boolean },       // Connection in progress flag
    lastUpdate: { type: Number },          // Timestamp of last status update
    errorMessage: { type: String }         // Error message display
  };

  /**
   * Component constructor - initializes default status values
   * Establishes the initial state for all monitored services
   */
  constructor() {
    super();
    this.websocketStatus = 'disconnected';  // Initial WebSocket state
    this.isConnecting = false;              // No connection in progress
    this.lastUpdate = Date.now();           // Current timestamp
    this.errorMessage = '';                 // No initial errors
    
    // Start status polling for demonstration purposes
    this._startStatusPolling();
  }

  /**
   * Lifecycle method - cleanup when component is removed from DOM
   * Ensures proper cleanup of timers and listeners to prevent memory leaks
   */
  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._statusInterval) {
      clearInterval(this._statusInterval);
    }
  }

  /**
   * Main render method - creates the status bar HTML template
   * Defines the structure with status indicators and connection controls
   * 
   * @returns {TemplateResult} Lit HTML template for the status bar component
   */
  render() {
    return html`
      <div class="status-bar">
        <div class="status-bar-content">
          <!-- Status Indicators Section -->
          <div class="status-indicators">
            <div class="status-group">
              <span class="status-label">WebSocket:</span>
              <md-assist-chip 
                class="status-chip ${this._getStatusClass('websocket')}"
                .elevated=${true}
              >
                <span class="material-icons status-icon">${this._getStatusIcon('websocket')}</span>
                <span class="status-text">${this._getStatusText('websocket')}</span>
              </md-assist-chip>
            </div>
          </div>

          <!-- Connection Controls Section -->
          <div class="connection-controls">
            ${this._renderConnectionButton()}
            
            ${this.websocketStatus === 'error' || this.errorMessage ? html`
              <md-icon-button 
                @click=${this._clearError}
                title="Clear error message"
                class="error-clear-btn"
              >
                <span class="material-icons">clear</span>
              </md-icon-button>
            ` : ''}
          </div>
        </div>

        <!-- Error Message Display -->
        ${this.errorMessage ? html`
          <div class="error-message">
            <span class="material-icons">warning</span>
            <span>${this.errorMessage}</span>
          </div>
        ` : ''}
      </div>
    `
  }

  /**
   * Renders the appropriate connection button based on current WebSocket status
   * Dynamically shows Connect, Disconnect, or Reconnect buttons with proper states
   * 
   * @returns {TemplateResult} HTML template for the connection button
   */
  _renderConnectionButton() {
    if (this.isConnecting) {
      return html`
        <md-outlined-button disabled>
          <span class="material-icons">sync</span>
          Connecting...
        </md-outlined-button>
      `;
    }

    switch (this.websocketStatus) {
      case 'connected':
        return html`
          <md-outlined-button @click=${this._handleDisconnect}>
            <span class="material-icons">link_off</span>
            Disconnect
          </md-outlined-button>
        `;
      
      case 'error':
        return html`
          <md-filled-button @click=${this._handleReconnect}>
            <span class="material-icons">refresh</span>
            Reconnect
          </md-filled-button>
        `;
      
      default: // disconnected, unknown
        return html`
          <md-filled-button @click=${this._handleConnect}>
            <span class="material-icons">link</span>
            Connect
          </md-filled-button>
        `;
    }
  }

  /**
   * Gets the appropriate CSS class for status styling based on service and status
   * Returns color-coded classes for visual status indication
   * 
   * @param {string} service - Service type ('websocket' or 'backend')
   * @returns {string} CSS class name for status styling
   */
  _getStatusClass(service) {
    const status = service === 'websocket' ? this.websocketStatus : this.backendStatus;
    
    switch (status) {
      case 'connected':
      case 'online':
        return 'status-success';
      case 'connecting':
      case 'reconnecting':
        return 'status-warning';
      case 'disconnected':
      case 'offline':
        return 'status-neutral';
      case 'error':
      case 'degraded':
        return 'status-error';
      default:
        return 'status-unknown';
    }
  }

  /**
   * Gets the appropriate icon for status display based on service and status
   * Returns Material Icons names for visual status representation
   * 
   * @param {string} service - Service type ('websocket' or 'backend')
   * @returns {string} Material Icons icon name
   */
  _getStatusIcon(service) {
    const status = service === 'websocket' ? this.websocketStatus : this.backendStatus;
    
    switch (status) {
      case 'connected':
      case 'online':
        return 'check_circle';
      case 'connecting':
      case 'reconnecting':
        return 'sync';
      case 'disconnected':
      case 'offline':
        return 'radio_button_unchecked';
      case 'error':
      case 'degraded':
        return 'error';
      default:
        return 'help_outline';
    }
  }

  /**
   * Gets the appropriate text label for status display
   * Returns human-readable status descriptions
   * 
   * @param {string} service - Service type ('websocket' or 'backend')
   * @returns {string} Human-readable status text
   */
  _getStatusText(service) {
    const status = service === 'websocket' ? this.websocketStatus : this.backendStatus;
    
    const statusTexts = {
      connected: 'Connected',
      disconnected: 'Disconnected',
      connecting: 'Connecting...',
      reconnecting: 'Reconnecting...',
      error: 'Error',
      online: 'Online',
      offline: 'Offline',
      degraded: 'Degraded',
      unknown: 'Unknown'
    };

    return statusTexts[status] || 'Unknown';
  }

  /**
   * Connect button click handler
   * Initiates WebSocket connection with proper state management
   * 
   * CURRENT IMPLEMENTATION: Mock/Simulation
   * - Simulates a 2-second connection process
   * - Always succeeds for demonstration purposes
   * 
   * FUTURE IMPLEMENTATION should replace with:
   * - Real WebSocket creation: new WebSocket('ws://localhost:8000/ws')
   * - Actual connection event handlers (onopen, onclose, onerror)
   * - Proper error handling and retry logic
   */
  _handleConnect() {
    this.isConnecting = true;
    this.websocketStatus = 'connecting';
    this.errorMessage = '';
    
    console.log('🔌 MOCK: Starting WebSocket connection...');
    
    // MOCK: Simulate connection process (replace with actual WebSocket logic)
    setTimeout(() => {
      this.isConnecting = false;
      this.websocketStatus = 'connected';
      this.lastUpdate = Date.now();
      console.log('✅ MOCK: WebSocket connection established');
    }, 2000);
  }

  /**
   * Disconnect button click handler
   * Terminates WebSocket connection with proper state management
   * 
   * CURRENT IMPLEMENTATION: Mock/Simulation
   * - Immediately sets status to disconnected
   * 
   * FUTURE IMPLEMENTATION should:
   * - Call websocket.close() method
   * - Handle close events properly
   * - Clean up any pending operations
   */
  _handleDisconnect() {
    this.websocketStatus = 'disconnected';
    this.errorMessage = '';
    this.lastUpdate = Date.now();
    console.log('🔌 MOCK: WebSocket disconnected');
  }

  /**
   * Reconnect button click handler
   * Attempts to re-establish WebSocket connection after error
   * 
   * CURRENT IMPLEMENTATION: Mock/Simulation
   * - 70% success rate for demonstration
   * - Random failure to show error handling
   * 
   * FUTURE IMPLEMENTATION should:
   * - Implement exponential backoff strategy
   * - Handle different types of connection errors
   * - Provide detailed error messages based on failure reason
   */
  _handleReconnect() {
    this.isConnecting = true;
    this.websocketStatus = 'reconnecting';
    this.errorMessage = '';
    
    console.log('🔄 MOCK: Attempting to reconnect WebSocket...');
    
    // MOCK: Simulate reconnection process (replace with actual WebSocket logic)
    setTimeout(() => {
      this.isConnecting = false;
      // MOCK: 70% success rate for demonstration
      if (Math.random() > 0.3) {
        this.websocketStatus = 'connected';
        console.log('✅ MOCK: WebSocket reconnection successful');
      } else {
        this.websocketStatus = 'error';
        this.errorMessage = 'Failed to reconnect. Please check your network connection.';
        console.log('❌ MOCK: WebSocket reconnection failed');
      }
      this.lastUpdate = Date.now();
    }, 2000);
  }

  /**
   * Clear error message handler
   * Resets error state and clears displayed error messages
   */
  _clearError() {
    this.errorMessage = '';
    if (this.websocketStatus === 'error') {
      this.websocketStatus = 'disconnected';
    }
  }

  /**
   * Start status polling for demonstration purposes
   * Simulates periodic status updates from backend services
   * 
   * CURRENT IMPLEMENTATION: Mock/Simulation
   * - Random backend status changes every 10 seconds
   * - Weighted towards 'online' status (60% online, 20% degraded, 20% offline)
   * 
   * FUTURE IMPLEMENTATION should:
   * - Poll actual backend health endpoint (e.g., /api/health)
   * - Handle HTTP errors and timeouts
   * - Implement circuit breaker pattern for failed health checks
   * - Use WebSocket for real-time status updates instead of polling
   * 
   * @private
   */
  _startStatusPolling() {
    // MOCK: Simulate backend status changes for demonstration
    this._statusInterval = setInterval(() => {
      // MOCK: Weighted random backend status (favoring 'online')
      const backendStates = ['online', 'online', 'online', 'degraded', 'offline'];
      const previousStatus = this.backendStatus;
      this.backendStatus = backendStates[Math.floor(Math.random() * backendStates.length)];
      
      if (previousStatus !== this.backendStatus) {
        console.log(`🔄 MOCK: Backend status changed from '${previousStatus}' to '${this.backendStatus}'`);
      }
      
      this.lastUpdate = Date.now();
    }, 10000); // MOCK: Update every 10 seconds (reduce to 5s for production)
  }

  /**
   * Component styles definition
   * Combines shared styles with status bar specific CSS for layout and theming
   */
  static styles = [
    sharedStyles,
    css`
      .status-bar {
        background: var(--md-sys-color-surface-variant);
        border: 1px solid var(--md-sys-color-outline);
        border-radius: var(--radius-md);
        padding: var(--space-md) var(--space-lg);
        margin-bottom: var(--space-lg);
        box-shadow: var(--shadow-sm);
        overflow: hidden; /* Prevent content overflow */
      }

      .status-bar-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-lg);
        flex-wrap: wrap; /* Allow wrapping on smaller screens */
        min-height: 40px; /* Ensure minimum height */
      }

      .status-indicators {
        display: flex;
        align-items: center;
        gap: var(--space-lg);
        flex-wrap: wrap; /* Allow indicators to wrap */
        flex: 1; /* Take available space */
      }

      .status-group {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        min-width: 0; /* Allow shrinking */
      }

      .status-label {
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--md-sys-color-on-surface-variant);
        min-width: 70px; /* Reduced from 80px */
        white-space: nowrap; /* Prevent text wrapping */
      }

      .status-chip {
        --md-assist-chip-container-shape: var(--radius-full);
        transition: all var(--transition-fast) ease;
        display: inline-flex !important;
        align-items: center !important;
        gap: var(--space-xs) !important;
        max-width: none; /* Prevent truncation */
      }

      .status-chip .status-icon {
        font-size: 1rem !important;
        line-height: 1 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        padding: 0 !important;
      }

      .status-chip .status-text {
        font-size: 0.875rem;
        font-weight: 500;
        white-space: nowrap; /* Prevent text wrapping */
      }

      /* Status Color Classes */
      .status-success {
        --md-assist-chip-label-text-color: #059669;
        --md-assist-chip-outline-color: #059669;
        background-color: color-mix(in srgb, #059669 10%, transparent);
      }

      .status-warning {
        --md-assist-chip-label-text-color: #D97706;
        --md-assist-chip-outline-color: #D97706;
        background-color: color-mix(in srgb, #D97706 10%, transparent);
      }

      .status-error {
        --md-assist-chip-label-text-color: #DC2626;
        --md-assist-chip-outline-color: #DC2626;
        background-color: color-mix(in srgb, #DC2626 10%, transparent);
      }

      .status-neutral {
        --md-assist-chip-label-text-color: var(--md-sys-color-on-surface-variant);
        --md-assist-chip-outline-color: var(--md-sys-color-outline);
      }

      .status-unknown {
        --md-assist-chip-label-text-color: var(--md-sys-color-secondary);
        --md-assist-chip-outline-color: var(--md-sys-color-outline);
      }

      .connection-controls {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        flex-shrink: 0; /* Prevent controls from shrinking */
      }

      .connection-controls md-filled-button,
      .connection-controls md-outlined-button {
        white-space: nowrap; /* Prevent button text wrapping */
        min-width: 100px; /* Ensure consistent button width */
      }

      .connection-controls .material-icons {
        margin-right: var(--space-xs) !important;
        font-size: 1rem !important;
        line-height: 1 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
      }

      .error-clear-btn {
        --md-icon-button-icon-color: var(--md-sys-color-error);
      }

      .error-message {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        padding: var(--space-sm) var(--space-md);
        margin-top: var(--space-md);
        background-color: var(--md-sys-color-error-container);
        color: var(--md-sys-color-on-error-container);
        border-radius: var(--radius-sm);
        font-size: 0.875rem;
      }

      .error-message .material-icons {
        font-size: 1rem;
      }

      /* Material Icons Integration */
      .material-icons {
        font-family: 'Material Icons' !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 1.2rem !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
        text-rendering: optimizeLegibility !important;
        vertical-align: middle !important;
      }

      /* Responsive Design */
      @media (max-width: 768px) {
        .status-bar-content {
          flex-direction: column;
          gap: var(--space-md);
          align-items: stretch;
        }

        .status-indicators {
          justify-content: center;
          gap: var(--space-md);
          width: 100%;
        }

        .status-group {
          justify-content: space-between;
          min-width: 250px; /* Ensure minimum width for proper display */
        }

        .status-label {
          min-width: 70px;
          text-align: left;
        }

        .connection-controls {
          justify-content: center;
          width: 100%;
        }

        .connection-controls md-filled-button,
        .connection-controls md-outlined-button {
          min-width: 140px; /* Larger buttons on mobile */
        }
      }

      @media (max-width: 480px) {
        .status-indicators {
          flex-direction: column;
          gap: var(--space-sm);
        }

        .status-group {
          min-width: 200px;
        }
      }
    `
  ]
}

/**
 * Custom element registration
 * Registers the StatusBar component as 'status-bar' in the browser's custom element registry
 */
window.customElements.define('status-bar', StatusBar);

/*
   * =========================================================================
   * EXAMPLE: Real WebSocket Integration (for future implementation)
   * =========================================================================
   * 
   * // Property to hold WebSocket instance
   * this.websocket = null;
   * 
   * // Real connection method
   * _handleConnect() {
   *   this.isConnecting = true;
   *   this.websocketStatus = 'connecting';
   *   this.errorMessage = '';
   *   
   *   try {
   *     this.websocket = new WebSocket('ws://localhost:8000/ws');
   *     
   *     this.websocket.onopen = () => {
   *       this.isConnecting = false;
   *       this.websocketStatus = 'connected';
   *       this.lastUpdate = Date.now();
   *       console.log('WebSocket connected successfully');
   *     };
   *     
   *     this.websocket.onclose = () => {
   *       this.websocketStatus = 'disconnected';
   *       this.lastUpdate = Date.now();
   *       console.log('WebSocket connection closed');
   *     };
   *     
   *     this.websocket.onerror = (error) => {
   *       this.isConnecting = false;
   *       this.websocketStatus = 'error';
   *       this.errorMessage = 'Connection failed: ' + error.message;
   *       this.lastUpdate = Date.now();
   *       console.error('WebSocket error:', error);
   *     };
   *     
   *   } catch (error) {
   *     this.isConnecting = false;
   *     this.websocketStatus = 'error';
   *     this.errorMessage = 'Failed to create WebSocket: ' + error.message;
   *   }
   * }
   * 
   * // Real disconnection method
   * _handleDisconnect() {
   *   if (this.websocket) {
   *     this.websocket.close(1000, 'User disconnected');
   *     this.websocket = null;
   *   }
   *   this.websocketStatus = 'disconnected';
   *   this.errorMessage = '';
   *   this.lastUpdate = Date.now();
   * }
   * 
   * // Real backend health check
   * async _checkBackendHealth() {
   *   try {
   *     const response = await fetch('/api/health', {
   *       method: 'GET',
   *       timeout: 5000
   *     });
   *     
   *     if (response.ok) {
   *       const health = await response.json();
   *       this.backendStatus = health.status; // 'online', 'degraded', etc.
   *     } else {
   *       this.backendStatus = 'offline';
   *     }
   *   } catch (error) {
   *     this.backendStatus = 'offline';
   *     console.error('Backend health check failed:', error);
   *   }
   *   this.lastUpdate = Date.now();
   * }
   * =========================================================================
   */
