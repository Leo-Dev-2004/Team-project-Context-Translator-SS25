/**
 * UI Component Module - Main Application Interface
 * 
 * This file contains the primary UI component for the Team Project Context Translator application.
 * It implements a tabbed interface using Lit web components and Material Design components,
 * providing the main user interface for setting up translation contexts, viewing AI explanations,
 * and managing application settings.
 * 
 * The component serves as the central hub of the application, orchestrating user interactions
 * across different functional areas through a clean tabbed interface. It integrates with
 * the explanation management system to display real-time AI-generated explanations and
 * provides comprehensive settings for customizing the translation experience.
 * 
 * Content:
 * - UI class: Main Lit web component with tabbed interface
 * - Setup tab: Domain configuration and language preferences
 * - Explanations tab: Display and management of AI explanations
 * - Settings management: Auto-save, real-time processing options
 * - Event handlers for user interactions
 * 
 * Structure:
 * - Import statements: Lit framework, Material Design components, shared modules
 * - UI class definition: Main component with reactive properties
 * - Constructor: Property initialization and explanation manager integration
 * - Lifecycle methods: Setup and cleanup for component lifecycle
 * - Render methods: Template rendering for different tabs and content
 * - Event handlers: User interaction processing
 * - Utility methods: Helper functions for data formatting and operations
 * - Styles: CSS-in-JS styling definitions
 * 
 * Key Features:
 * - Tabbed navigation (Setup, Explanations)
 * - Domain and language configuration
 * - Real-time explanation display and management
 * - Material Design component integration
 * - Responsive design with accessibility considerations
 * - Integration with explanation manager for state synchronization
 * 
 * Dependencies:
 * - Lit: Web component framework
 * - Material Web: Google's Material Design web components
 * - Shared styles and explanation management modules
 * 
 * DISCLAIMER: Some portions of this code may have been generated or assisted by AI tools.
 */

// Import Lit framework core components for web component creation
import { LitElement, css, html } from 'lit'

// Import shared styling configurations for consistent theming across components
import { sharedStyles } from './styles.js'

// Import explanation item component for displaying individual explanations
import './explanation-item.js'

// Import explanation manager for handling explanation state and operations
import { explanationManager } from './explanation-manager.js'

// Import Material Design web components for consistent UI design
import '@material/web/tabs/tabs.js'
import '@material/web/tabs/primary-tab.js'
import '@material/web/button/filled-button.js'
import '@material/web/button/outlined-button.js'
import '@material/web/button/text-button.js'
import '@material/web/textfield/outlined-text-field.js'
import '@material/web/iconbutton/icon-button.js'
import '@material/web/switch/switch.js'
import '@material/web/select/outlined-select.js'
import '@material/web/select/select-option.js'
//Import for the Universal Message Parser
import { UniversalMessageParser } from './universal-message-parser.js'
/**
 * Main UI Component - Context Translator Application Interface
 * 
 * A comprehensive web component that provides the primary user interface for the
 * Context Translator application. Features a tabbed interface with setup configuration,
 * AI explanation display, and settings management.
 * 
 * @extends LitElement
 */
export class UI extends LitElement {
  /**
   * Reactive properties that trigger re-rendering when changed
   * Defines the component's state and data binding capabilities
   */
  static properties = {
    activeTab: { type: Number },           // Currently selected tab index
    domainValue: { type: String },         // User's domain/context description
    autoSave: { type: Boolean },          // Auto-save setting toggle
    selectedLanguage: { type: String },    // User's preferred language
    explanations: { type: Array }          // Array of AI-generated explanations
  };

  /**
   * Component constructor - initializes default values and sets up explanation manager
   * Establishes the initial state and creates listeners for explanation updates
   */
  constructor() {
    super();
    this.activeTab = 0
    this.domainValue = ''
    this.autoSave = false
    this.selectedLanguage = 'en'
    this.explanations = [];
    
    this._explanationListener = (explanations) => {
      this.explanations = [...explanations];
    };
    explanationManager.addListener(this._explanationListener);
  }

  /**
   * Lifecycle method - cleanup when component is removed from DOM
   * Ensures proper cleanup of event listeners to prevent memory leaks
   */
  disconnectedCallback() {
    super.disconnectedCallback();
    explanationManager.removeListener(this._explanationListener);
  }

  /**
   * Main render method - creates the component's HTML template
   * Defines the overall structure with header, tabs, and dynamic content
   * 
   * @returns {TemplateResult} Lit HTML template for the component
   */  render() {
    return html`
      <div class="ui-host">
        <div class="ui-app-container">
          <!-- App Title and Description Header -->
          <header class="app-header ocean-header">
            <h1 class="display-medium">Context Translator</h1>
            <p class="body-large">Real-time meeting explanations and summaries powered by AI.</p>
          </header>

          <!-- Material Design Tabs Navigation -->
          <md-tabs @change=${this._onTabChange} .activeTabIndex=${this.activeTab}>
            <md-primary-tab>Setup</md-primary-tab>
            <md-primary-tab>Explanations</md-primary-tab>
          </md-tabs>

          <!-- Dynamic Tab Content Container -->
          <div class="tab-content">
            ${this._renderTabContent()}
          </div>
        </div>
      </div>
    `
  }

  /**
   * Renders content for the currently active tab
   * Uses switch statement to determine which tab content to display
   * 
   * @returns {TemplateResult} HTML template for the active tab's content
   */
  _renderTabContent() {
    switch (this.activeTab) {
      case 0:
        return html`
          <div class="tab-panel setup-panel">
            <div class="setup-content">
              <h2 class="headline-medium ocean-accent-text setup-title">Setup Your Translation Context</h2>
              <div class="input-section">
                <h3 class="title-medium section-title">Domain Description</h3>
                <p class="body-medium section-description">
                  Describe your field or context to improve translation accuracy
                  (e.g., "CS student", "primary school teacher", "medical professional")
                </p>                <div class="domain-input-group">
                  <md-outlined-text-field
                    label="Your domain or context"
                    .value=${this.domainValue}
                    @input=${this._onDomainInput}
                    placeholder="e.g., computer science student, medical professional, software engineer..."
                    class="domain-field"
                    type="textarea"
                    rows="3"
                    supporting-text="Describe your field or expertise to improve AI explanations"
                  >
                    ${this.domainValue ? html`
                      <md-icon-button slot="trailing-icon" @click=${this._clearDomain} title="Clear text">
                        <span class="material-icons">clear</span>
                      </md-icon-button>
                    ` : ''}
                  </md-outlined-text-field>
                </div></div>

              <div class="spacer"></div>

              <div class="action-buttons">
                <md-filled-button @click=${this._saveSettings}>
                  Save Configuration
                </md-filled-button>
                <md-outlined-button @click=${this._resetSettings}>
                  Reset to Defaults
                </md-outlined-button>
              </div>
            </div>
          </div>
        `
      case 1:
        return html`
          <div class="tab-panel explanations-panel">
            <div class="explanations-header">
              <h2 class="headline-medium ocean-accent-text">AI Explanations</h2>
              <p class="body-large">Terms and concepts explained during your meetings</p>                <div class="explanations-controls">
                <md-text-button @click=${this._clearAllExplanations}>
                  <span class="material-icons">delete</span> Clear All
                </md-text-button>
                <md-filled-button @click=${this._addTestExplanation}>
                  <span class="material-icons">add</span> Add Test
                </md-filled-button>
              </div>
            </div>

            <div class="explanations-content">              
              ${this.explanations.length === 0 
                ? html`                  <div class="empty-state">
                    <h3 class="title-medium">No explanations yet</h3>
                    <p class="body-medium">Join a meeting and our AI will automatically explain complex terms and concepts.</p>
                  </div>
                `
                : html`
                  <div class="explanations-list">
                    ${this.explanations.map(explanation => html`
                      <explanation-item
                        .explanation=${explanation}
                        .onPin=${this._handlePin.bind(this)}
                        .onDelete=${this._handleDelete.bind(this)}
                        .onCopy=${this._handleCopy.bind(this)}
                      ></explanation-item>
                    `)}
                  </div>
                `
              }
            </div>
          </div>
        `
      default:
        return html`<div class="tab-panel">Select a tab</div>`
    }
  }

  /**
   * Tab change event handler
   * Updates the active tab index when user clicks on a different tab
   * 
   * @param {Event} event - Tab change event from md-tabs component
   */
  _onTabChange(event) {
    this.activeTab = event.target.activeTabIndex
  }

  /**
   * Domain input event handler
   * Updates domain value as user types in the domain text field
   * 
   * @param {Event} event - Input event from domain text field
   */
  _onDomainInput(event) {
    this.domainValue = event.target.value
  }

  /**
   * Clear domain button click handler
   * Resets the domain value to empty string
   */
  _clearDomain() {
    this.domainValue = ''
  }

  /**
   * Language selection change handler
   * Updates selected language when user chooses from dropdown
   * 
   * @param {Event} event - Change event from language select component
   */
  _onLanguageChange(event) {
    this.selectedLanguage = event.target.value
  }

  /**
   * Auto-save toggle change handler
   * Updates auto-save setting when user toggles the switch
   * 
   * @param {Event} event - Change event from auto-save switch component
   */
  _onAutoSaveChange(event) {
    this.autoSave = event.target.selected
  }

  /**
   * Save settings button click handler
   * Logs current settings (placeholder for actual save functionality)
   */
  _saveSettings() {
    console.log('Settings saved:', {
      domain: this.domainValue,
      language: this.selectedLanguage,
      autoSave: this.autoSave,
    })
  }

  /**
   * Reset settings button click handler
   * Restores all settings to their default values
   */
  _resetSettings() {
    this.domainValue = ''
    this.selectedLanguage = 'en'
    this.autoSave = false
  }

  /**
   * Pin explanation handler
   * Delegates to explanation manager to pin/unpin an explanation
   * 
   * @param {string} id - Unique identifier of the explanation to pin
   */
  _handlePin(id) {
    explanationManager.pinExplanation(id);
  }

  /**
   * Delete explanation handler
   * Delegates to explanation manager to remove an explanation
   * 
   * @param {string} id - Unique identifier of the explanation to delete
   */
  _handleDelete(id) {
    explanationManager.deleteExplanation(id);
  }

  /**
   * Copy explanation handler
   * Copies explanation content to clipboard in formatted text
   * 
   * @param {Object} explanation - Explanation object containing title, content, and timestamp
   */
  _handleCopy(explanation) {
    const textToCopy = `**${explanation.title}**\n\n${explanation.content}\n\n---\n${this._formatTimestamp(explanation.timestamp)}`;
    
    navigator.clipboard.writeText(textToCopy).then(() => {
      this._showNotification?.('Explanation copied to clipboard!');
    }).catch(err => {
      console.error('Failed to copy:', err);
      this._showNotification?.('Failed to copy explanation', 'error');
    });
  }

  /**
   * Clear all explanations handler
   * Shows confirmation dialog and clears all explanations if confirmed
   */
  _clearAllExplanations() {
    if (confirm('Are you sure you want to clear all explanations?')) {
      explanationManager.clearAll();
    }
  }

  /**
   * Add test explanation handler (Development utility)
   * Adds predefined test explanations for development and testing purposes
   */
  _addTestExplanation() {
    const testExplanations = [
      {
        title: "Machine Learning",
        content: "**Machine Learning** is a subset of artificial intelligence (AI) that enables computers to learn and improve from experience without being explicitly programmed.\n\n*Key concepts:*\n- **Supervised Learning**: Learning with labeled data\n- **Unsupervised Learning**: Finding patterns in unlabeled data\n- **Neural Networks**: Computing systems inspired by biological neural networks\n\nMachine learning algorithms build mathematical models based on training data to make predictions or decisions."
      },
      {
        title: "API",
        content: "**API (Application Programming Interface)** is a set of protocols, routines, and tools for building software applications.\n\n*Think of it as:*\nA waiter in a restaurant who takes your order (request) to the kitchen (server) and brings back your food (response).\n\n**Common types:**\n- REST APIs\n- GraphQL APIs\n- WebSocket APIs"
      }
    ];

    const randomExplanation = testExplanations[Math.floor(Math.random() * testExplanations.length)];
    explanationManager.addExplanation(
      randomExplanation.title,
      randomExplanation.content
    );
  }

  /**
   * Format timestamp utility method
   * Converts timestamp to localized date and time string
   * 
   * @param {number} timestamp - Unix timestamp to format
   * @returns {string} Formatted date and time string in German locale
   */
  _formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Component styles definition
   * Combines shared styles with component-specific CSS for layout and theming
   */
  static styles = [sharedStyles]
}

/**
 * Custom element registration
 * Registers the UI component as 'my-element' in the browser's custom element registry
 */
window.customElements.define('my-element', UI)