/**
 * UI Component Module - Main Application Interface
 */

import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import './explanation-item.js';
import { explanationManager } from './explanation-manager.js';

// Import Material Design web components
import '@material/web/tabs/tabs.js';
import '@material/web/tabs/primary-tab.js';
import '@material/web/button/filled-button.js';
import '@material/web/button/outlined-button.js';
import '@material/web/button/text-button.js';
import '@material/web/textfield/outlined-text-field.js';
import '@material/web/iconbutton/icon-button.js';
import '@material/web/switch/switch.js';
import '@material/web/select/outlined-select.js';
import '@material/web/select/select-option.js';

export class UI extends LitElement {
  static properties = {
    activeTab: { type: Number },
    domainValue: { type: String },
    autoSave: { type: Boolean },
    selectedLanguage: { type: String },
    explanations: { type: Array },
  };

  constructor() {
    super();
    this.activeTab = 0;
    this.domainValue = '';
    this.autoSave = false;
    this.selectedLanguage = 'en';
    this.explanations = [];
    
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
      <div class="ui-host">
        <div class="ui-app-container">
          <header class="app-header ocean-header">
            <h1 class="display-medium">Context Translator</h1>
            <p class="body-large">Real-time meeting explanations and summaries powered by AI.</p>
          </header>

          <md-tabs @change=${this._onTabChange} .activeTabIndex=${this.activeTab}>
            <md-primary-tab>Setup</md-primary-tab>
            <md-primary-tab>Explanations</md-primary-tab>
          </md-tabs>

          <div class="tab-content">
            ${this._renderTabContent()}
          </div>
        </div>
      </div>
    `;
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
                  Describe your field or context to improve translation accuracy.
                </p>
                <div class="domain-input-group">
                  <md-outlined-text-field
                    label="Your domain or context"
                    .value=${this.domainValue}
                    @input=${this._onDomainInput}
                    class="domain-field"
                    type="textarea"
                    rows="3"
                  >
                  </md-outlined-text-field>
                </div>
              </div>

              <div class="spacer"></div>

              <div class="action-buttons">
                <md-filled-button @click=${this._saveSettings}>
                  Save Configuration
                </md-filled-button>
                <md-outlined-button @click=${this._resetSettings}>
                  Reset to Defaults
                </md-outlined-button>
                
                <div class="session-controls">
                  <md-filled-button id="start-session-button" @click=${this._startSession}>
                    Session erstellen
                  </md-filled-button>
                  <md-outlined-text-field
                    id="session-code-input"
                    label="Session Code"
                    placeholder="Code eingeben..."
                  ></md-outlined-text-field>
                  <md-outlined-button id="join-session-button" @click=${this._joinSession}>
                    Session beitreten
                  </md-outlined-button>
                </div>
              </div>
            </div>
          </div>
        `;
      case 1:
        // WIEDERHERGESTELLT: Vollständige UI für den "Explanations"-Tab
        return html`
          <div class="tab-panel explanations-panel">
            <div class="explanations-header">
              <h2 class="headline-medium ocean-accent-text">AI Explanations</h2>
              <p class="body-large">Terms and concepts explained during your meetings</p>
                <div class="explanations-controls">
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
                ? html`
                  <div class="empty-state">
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
        `;
      default:
        return html`<div class="tab-panel">Select a tab</div>`;
    }
  }

  // ### Event Handlers & Methods ###

  _startSession() {
    alert("FEHLER: Die alte _startSession in ui.js wird aufgerufen!");
    console.warn('UI: _startSession() clicked, but not implemented...');
}


  _onTabChange(event) {
    this.activeTab = event.target.activeTabIndex;
  }

  _onDomainInput(event) {
    this.domainValue = event.target.value;
  }

  _saveSettings() {
    console.log('Settings saved:', { domain: this.domainValue });
  }

  _resetSettings() {
    this.domainValue = '';
  }

  _startSession() {
    console.warn('UI: _startSession() clicked, but not implemented. Must be overridden in child class.');
  }

  _joinSession() {
    console.warn('UI: _joinSession() clicked, but not implemented. Must be overridden in child class.');
  }

  // WIEDERHERGESTELLT: Fehlende Methoden für den "Explanations"-Tab
  _handlePin(id) {
    explanationManager.pinExplanation(id);
  }

  _handleDelete(id) {
    explanationManager.deleteExplanation(id);
  }

  _handleCopy(explanation) {
    const textToCopy = `**${explanation.title}**\n\n${explanation.content}`;
    navigator.clipboard.writeText(textToCopy).then(() => {
      // Annahme: _showNotification existiert in der erbenden Klasse renderer.js
      this._showNotification?.('Explanation copied!');
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  }

  _clearAllExplanations() {
    if (confirm('Are you sure you want to clear all explanations?')) {
      explanationManager.clearAll();
    }
  }

  _addTestExplanation() {
    explanationManager.addExplanation(
      "Test Explanation",
      "This is the content for the test explanation added via the UI button."
    );
  }
  
  // ### Styles ###
  static styles = [
    sharedStyles,
    css`
      .session-controls {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 24px;
        border-top: 1px solid var(--md-sys-color-outline-variant);
        padding-top: 24px;
      }
    `
  ];
}

// window.customElements.define('my-element', UI);