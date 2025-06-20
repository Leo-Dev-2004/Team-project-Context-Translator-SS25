import { LitElement, css, html } from 'lit'
import { sharedStyles } from './styles.js'
import './explanation-item.js'
import { explanationManager } from './explanation-manager.js'
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

/**
 * An app element with Material Design components.
 *
 * @slot - This element has a slot
 */
export class UI extends LitElement {
  static properties = {
    activeTab: { type: Number },
    domainValue: { type: String },
    autoSave: { type: Boolean },
    selectedLanguage: { type: String },
    explanations: { type: Array }
  };

  constructor() {
    super();
    this.activeTab = 0
    this.domainValue = ''
    this.autoSave = false
    this.selectedLanguage = 'en'
    this.explanations = [];
    
    // Explanations Manager Setup
    this._explanationListener = (explanations) => {
      this.explanations = [...explanations];
    };
    explanationManager.addListener(this._explanationListener);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    explanationManager.removeListener(this._explanationListener);
  }

  render() {
    return html`
      <div class="app-container">
        <!-- App Title -->
        <header class="app-header ocean-header">
          <h1 class="display-medium">Context Translator</h1>
          <p class="body-large">Real-time meeting explanations and summaries powered by AI.</p>
        </header>

        <!-- Material Tabs -->
        <md-tabs @change=${this._onTabChange} .activeTabIndex=${this.activeTab}>
          <md-primary-tab>Setup</md-primary-tab>
          <md-primary-tab>Explanations</md-primary-tab>
          <md-primary-tab>Summaries</md-primary-tab>
        </md-tabs>

        <!-- Tab Content -->
        <div class="tab-content">
          ${this._renderTabContent()}
        </div>
      </div>
    `
  }

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
                </p>
                <div class="domain-input-group">
                  <md-outlined-text-field
                    label="Your domain or context"
                    .value=${this.domainValue}
                    @input=${this._onDomainInput}
                    placeholder="e.g., computer science student"
                    class="domain-field"
                  ></md-outlined-text-field>
                  ${this.domainValue
                    ? html`
                        <md-icon-button @click=${this._clearDomain} class="clear-button">
                          <span class="material-icons">close</span>
                        </md-icon-button>
                      `
                    : ''}
                </div>
              </div>

              <div class="input-section">
                <h3 class="title-medium section-title">Language Preferences</h3>
                <md-outlined-select
                  label="Primary Language"
                  .value=${this.selectedLanguage}
                  @change=${this._onLanguageChange}
                >
                  <md-select-option value="en">English</md-select-option>
                  <md-select-option value="de">German</md-select-option>
                  <md-select-option value="es">Spanish</md-select-option>
                  <md-select-option value="fr">French</md-select-option>
                  <md-select-option value="it">Italian</md-select-option>
                </md-outlined-select>
              </div>

              <div class="input-section">
                <h3 class="title-medium section-title">General Settings</h3>
                <div class="setting-item">
                  <div class="setting-info">
                    <span class="label-large">Auto-save translations</span>
                    <span class="body-small setting-description">Automatically save all translations to your history</span>
                  </div>
                  <md-switch
                    .selected=${this.autoSave}
                    @change=${this._onAutoSaveChange}
                  ></md-switch>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <span class="label-large">Real-time processing</span>
                    <span class="body-small setting-description">Process audio in real-time for instant translations</span>
                  </div>
                  <md-switch selected></md-switch>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <span class="label-large">Confidence indicators</span>
                    <span class="body-small setting-description">Show confidence levels for each translation</span>
                  </div>
                  <md-switch></md-switch>
                </div>
              </div>

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
              <p class="body-large">Terms and concepts explained during your meetings</p>              <div class="explanations-controls">
                <md-text-button @click=${this._clearAllExplanations}>
                  🗑️ Clear All
                </md-text-button>
                <md-filled-button @click=${this._addTestExplanation}>
                  ➕ Add Test
                </md-filled-button>
              </div>
            </div>

            <div class="explanations-content">              ${this.explanations.length === 0 
                ? html`
                  <div class="empty-state">
                    <div class="empty-icon">❓</div>
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

  _onTabChange(event) {
    this.activeTab = event.target.activeTabIndex
  }

  _onDomainInput(event) {
    this.domainValue = event.target.value
  }

  _clearDomain() {
    this.domainValue = ''
  }

  _onLanguageChange(event) {
    this.selectedLanguage = event.target.value
  }

  _onAutoSaveChange(event) {
    this.autoSave = event.target.selected
  }

  _saveSettings() {
    console.log('Settings saved:', {
      domain: this.domainValue,
      language: this.selectedLanguage,
      autoSave: this.autoSave,
    })
  }

  _resetSettings() {
    this.domainValue = ''
    this.selectedLanguage = 'en'
    this.autoSave = false
  }

  // Explanation Event Handlers
  _handlePin(id) {
    explanationManager.pinExplanation(id);
  }

  _handleDelete(id) {
    explanationManager.deleteExplanation(id);
  }

  _handleCopy(explanation) {
    const textToCopy = `**${explanation.title}**\n\n${explanation.content}\n\n---\n${this._formatTimestamp(explanation.timestamp)}`;
    
    navigator.clipboard.writeText(textToCopy).then(() => {
      this._showNotification?.('Explanation copied to clipboard!');
    }).catch(err => {
      console.error('Failed to copy:', err);
      this._showNotification?.('Failed to copy explanation', 'error');
    });
  }

  _clearAllExplanations() {
    if (confirm('Are you sure you want to clear all explanations?')) {
      explanationManager.clearAll();
    }
  }

  _addTestExplanation() {
    // Test-Funktion für Entwicklung
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

  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        background-color: var(--md-sys-color-surface);
        color: var(--md-sys-color-on-surface);
        font-family: var(--md-sys-typescale-body-large-font, 'Roboto', sans-serif);
        min-height: 100vh;
      }

      .app-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }

      :focus {
        outline: 3px solid var(--md-sys-color-primary);
        outline-offset: 2px;
      }

      .explanations-panel {
        max-width: 100%;
        padding: 24px;
      }

      .explanations-header {
        margin-bottom: 32px;
      }

      .explanations-controls {
        display: flex;
        gap: 12px;
        margin-top: 16px;
        flex-wrap: wrap;
      }

      .explanations-content {
        max-height: 70vh;
        overflow-y: auto;
        padding-right: 8px;
      }

      .explanations-list {
        display: flex;
        flex-direction: column;
        gap: 0;
      }

      .empty-state {
        text-align: center;
        padding: 64px 24px;
        color: var(--md-sys-color-on-surface-variant);
      }

      .empty-icon {
        font-size: 72px;
        margin-bottom: 16px;
        opacity: 0.6;
      }

      .empty-state h3 {
        margin: 16px 0 8px 0;
      }

      .empty-state p {
        max-width: 400px;
        margin: 0 auto;
      }

      /* Scrollbar Styling */
      .explanations-content::-webkit-scrollbar {
        width: 6px;
      }

      .explanations-content::-webkit-scrollbar-track {
        background: var(--md-sys-color-surface-container);
        border-radius: 3px;
      }

      .explanations-content::-webkit-scrollbar-thumb {
        background: var(--md-sys-color-outline-variant);
        border-radius: 3px;
      }

      .explanations-content::-webkit-scrollbar-thumb:hover {
        background: var(--md-sys-color-outline);
      }
    `
  ]
}

window.customElements.define('my-element', UI)