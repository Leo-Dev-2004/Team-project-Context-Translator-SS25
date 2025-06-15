import { LitElement, css, html } from 'lit'
import { sharedStyles } from './styles.js'
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
export class MyElement extends LitElement {
  static get properties() {
    return {
      activeTab: { type: Number },
      domainValue: { type: String },
      autoSave: { type: Boolean },
      selectedLanguage: { type: String },
    }
  }

  constructor() {
    super()
    this.activeTab = 0
    this.domainValue = ''
    this.autoSave = false
    this.selectedLanguage = 'en'
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
          <md-primary-tab>Translator</md-primary-tab>
          <md-primary-tab>Settings</md-primary-tab>
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
          <div class="tab-panel ocean-card">
            <h2 class="headline-medium ocean-accent-text">Translation Settings</h2>
            <p class="body-large">Configure your translation preferences.</p>
            <div class="button-group">
              <md-filled-button @click=${this._onConfigureClick}>
                Configure Languages
              </md-filled-button>
              <md-text-button @click=${this._onResetClick}>
                Reset to Default
              </md-text-button>
            </div>
          </div>
        `
      case 2:
        return html`
          <div class="tab-panel ocean-card">
            <h2 class="headline-medium ocean-accent-text">Application Settings</h2>
            <p class="body-large">Manage your app preferences and account.</p>
            <div class="button-group">
              <md-outlined-button @click=${this._onPreferencesClick}>
                Preferences
              </md-outlined-button>
              <md-outlined-button @click=${this._onAccountClick}>
                Account Settings
              </md-outlined-button>
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

  _onConfigureClick() {}
  _onResetClick() {}
  _onPreferencesClick() {}
  _onAccountClick() {}

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
    `
  ]
}

window.customElements.define('my-element', MyElement)