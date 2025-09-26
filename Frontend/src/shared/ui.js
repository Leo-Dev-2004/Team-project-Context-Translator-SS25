// flattened copy adapted from shared/src/ui.js
import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import './explanation-item.js';
import { explanationManager } from './explanation-manager.js';
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
import '@material/web/dialog/dialog.js';
import './status-bar.js';

export class UI extends LitElement {
  static properties = {
    activeTab: { type: Number },
    domainValue: { type: String },
    explanationStyle: { type: String },
    explanations: { type: Array },
    isWindows: { type: Boolean },
    manualTerm: { type: String },
    serverStatus: { type: String },
    microphoneStatus: { type: String },
    isDarkMode: { type: Boolean },
    scrollbarStyle: { type: String }
  };
  constructor() {
    super();
    this.activeTab = 0;
    this.domainValue = '';
    this.explanationStyle = 'detailed';
    this.explanations = [];
    this.isWindows = false;
    this.manualTerm = '';
    this.serverStatus = 'initializing';
    this.microphoneStatus = 'initializing';
    this.isDarkMode = null;
    this.scrollbarStyle = 'minimal'; // null = system preference, true/false = user override
    this._lastExplanationUpdate = 0;
    this._explanationUpdateThrottle = 100; // Throttle UI updates to every 100ms
    this._explanationListener = (exps) => {
      const now = Date.now();
      if (now - this._lastExplanationUpdate >= this._explanationUpdateThrottle) {
        this.explanations = [...exps];
        this._lastExplanationUpdate = now;
      } else {
        // Debounce rapid updates
        clearTimeout(this._explanationUpdateTimeout);
        this._explanationUpdateTimeout = setTimeout(() => {
          this.explanations = [...exps];
          this._lastExplanationUpdate = Date.now();
        }, this._explanationUpdateThrottle);
      }
    };
    explanationManager.addListener(this._explanationListener);
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    explanationManager.removeListener(this._explanationListener);
    clearTimeout(this._explanationUpdateTimeout);
  }

  render() {
    return html`<div class="ui-host">
      ${this.isWindows ? html`<div class="titlebar" part="titlebar">
        <div class="window-controls">
          <button class="win-btn minimize" title="Minimize" @click=${this._winMinimize}>
            <span class="material-icons">remove</span>
          </button>
          <button class="win-btn maximize" title="Maximize" @click=${this._winToggleMaximize}>
            <span class="material-icons" id="maximize-icon">crop_square</span>
          </button>
          <button class="win-btn close" title="Close" @click=${this._winClose}>
            <span class="material-icons">close</span>
          </button>
        </div>
      </div>` : ''}
      <md-dialog id="session-dialog">
        <div slot="headline">Session Created!</div>
        <div slot="content">Share this code with other participants to join:
          <h2 id="dialog-session-code" class="dialog-code"></h2>
        </div>
        <div slot="actions">
          <md-text-button @click=${() => this.shadowRoot.querySelector('#session-dialog').close()}>Close</md-text-button>
        </div>
      </md-dialog>
      <div class="ui-app-container">
        <header class="app-header ocean-header">
          <div class="theme-toggle" title="Cycle through: System → Light → Dark">
            <span class="theme-icon material-icons">
              ${this.isDarkMode === null ? 'brightness_auto' : 
                this.isDarkMode ? 'dark_mode' : 'light_mode'}
            </span>
            <md-switch 
              ?selected=${this.isDarkMode === true}
              @click=${this._onThemeToggle}
              aria-label="Theme toggle">
            </md-switch>
          </div>
          <h1 class="display-medium">Context Translator</h1>
          <p class="body-large">Real-time meeting explanations and summaries powered by AI.</p>
        </header>
        <status-bar 
          .serverStatus=${this.serverStatus}
          .microphoneStatus=${this.microphoneStatus}
        ></status-bar>
        <md-tabs @change=${this._onTabChange} .activeTabIndex=${this.activeTab}>
          <md-primary-tab>Setup</md-primary-tab>
          <md-primary-tab>Explanations</md-primary-tab>
        </md-tabs>
        <div class="tab-content">${this._renderTabContent()}</div>
      </div>
    </div>`;
  }
  _renderTabContent() {
    switch (this.activeTab) {
      case 0:
        return html`<div class="tab-panel setup-panel">
          <div class="setup-content">
            <h2 class="headline-medium ocean-accent-text setup-title">Setup Your Translation Context</h2>
            <div class="input-section">
              <h3 class="title-medium section-title">Domain Description</h3>
              <p class="body-medium section-description">Describe your field or context to improve translation accuracy.</p>
              <div class="domain-input-group">
                <md-outlined-text-field label="Your domain or context" .value=${this.domainValue} @input=${this._onDomainInput} class="domain-field" type="textarea" rows="3"></md-outlined-text-field>
              </div>
            </div>
            <div class="input-section">
              <h3 class="title-medium section-title">Explanation Style</h3>
              <p class="body-medium section-description">Choose how detailed you want the AI explanations to be.</p>
              <div class="style-input-group">
                <md-outlined-select .value=${this.explanationStyle} @change=${this._onExplanationStyleChange} class="style-field">
                  <md-select-option value="simple">
                    <div slot="headline">Simple</div>
                    <div slot="supporting-text">Brief, easy-to-understand explanations</div>
                  </md-select-option>
                  <md-select-option value="detailed">
                    <div slot="headline">Detailed</div>
                    <div slot="supporting-text">Comprehensive explanations with examples</div>
                  </md-select-option>
                  <md-select-option value="technical">
                    <div slot="headline">Technical</div>
                    <div slot="supporting-text">In-depth technical explanations</div>
                  </md-select-option>
                  <md-select-option value="beginner">
                    <div slot="headline">Beginner</div>
                    <div slot="supporting-text">Explanations for complete beginners</div>
                  </md-select-option>
                </md-outlined-select>
              </div>
            </div>
            <div class="input-section">
              <h3 class="title-medium section-title">Scrollbar Style</h3>
              <p class="body-medium section-description">Choose how scrollbars appear in the application.</p>
              <div class="style-input-group">
                <md-outlined-select .value=${this.scrollbarStyle} @change=${this._onScrollbarStyleChange} class="style-field">
                  <md-select-option value="minimal">
                    <div slot="headline">Minimal</div>
                    <div slot="supporting-text">Thin, subtle scrollbars that don't distract</div>
                  </md-select-option>
                  <md-select-option value="glassy">
                    <div slot="headline">Glassy</div>
                    <div slot="supporting-text">Semi-transparent scrollbars with blur effect</div>
                  </md-select-option>
                  <md-select-option value="hidden">
                    <div slot="headline">Hidden</div>
                    <div slot="supporting-text">Completely hide scrollbars (scroll with mouse/trackpad)</div>
                  </md-select-option>
                  <md-select-option value="default">
                    <div slot="headline">Default</div>
                    <div slot="supporting-text">Use browser default scrollbars</div>
                  </md-select-option>
                </md-outlined-select>
              </div>
            </div>
            <div class="spacer"></div>
            <div class="action-buttons">
              <md-filled-button @click=${this._saveSettings}>Save Configuration</md-filled-button>
              <md-outlined-button @click=${this._resetSettings}>Reset to Defaults</md-outlined-button>
              <div class="session-controls">
                <md-outlined-text-field id="session-code-input" label="Session Code" placeholder="Code eingeben..."></md-outlined-text-field>
                <md-filled-button id="start-session-button" @click=${this._startSession}>Session erstellen</md-filled-button>
                <md-outlined-button id="join-session-button" @click=${this._joinSession}>Session beitreten</md-outlined-button>
              </div>
            </div>
          </div>
        </div>`;
      case 1:
        return html`<div class="tab-panel explanations-panel">
          <div class="explanations-header">
            <h2 class="headline-medium ocean-accent-text">AI Explanations</h2>
            <div class="explanations-controls">
              <md-outlined-text-field id="manual-term-input" class="manual-term-input" label="Explain a term" placeholder="e.g. OAuth, ROI, Kafka" .value=${this.manualTerm} @input=${this._onManualTermInput} @keydown=${this._onManualKeyDown}>
                <md-icon-button id="manual-send-button" slot="trailing-icon" class="accent" title="Send" aria-label="Send" @click=${this._sendManualRequest} ?disabled=${!(this.manualTerm && this.manualTerm.trim())}>
                  <span class="material-icons">send</span>
                </md-icon-button>
              </md-outlined-text-field>
              <md-outlined-button @click=${this._clearAllExplanations}>
                <span class="material-icons" slot="icon">delete</span>
                Clear All
              </md-outlined-button>
            </div>
          </div>
          <div class="explanations-content">
            ${this.explanations.length === 0 ? html`<div class="empty-state"><p>No explanations yet. Ask for an explanation or wait for one to be generated.</p></div>` : html`<div class="explanations-list">
              ${this.explanations.map(explanation => html`<explanation-item .explanation=${explanation} .onPin=${this._handlePin.bind(this)} .onDelete=${this._handleDelete.bind(this)} .onCopy=${this._handleCopy.bind(this)} .onRegenerate=${this._handleRegenerate.bind(this)}></explanation-item>`)}
            </div>`}
          </div>
        </div>`;
      default:
        return html`<div class="tab-panel">Select a tab</div>`;
    }
  }
  _onTabChange(e) { this.activeTab = e.target.activeTabIndex; }
  _onDomainInput(e) { this.domainValue = e.target.value; }
  _onExplanationStyleChange(e) { this.explanationStyle = e.target.value; }
  _onScrollbarStyleChange(e) { 
    this.scrollbarStyle = e.target.value; 
    this._applyScrollbarStyle();
  }
  async _saveSettings() { 
    if (window.electronAPI) {
      const result = await window.electronAPI.saveSettings({ 
        domain: this.domainValue,
        explanationStyle: this.explanationStyle,
        scrollbarStyle: this.scrollbarStyle
      });
      if (result.success) {
        console.log('Settings saved successfully:', { domain: this.domainValue, explanationStyle: this.explanationStyle, scrollbarStyle: this.scrollbarStyle });
        this._showNotificationIfAvailable?.('Settings saved successfully', 'success');
      } else {
        console.error('Failed to save settings:', result.error);
        this._showNotificationIfAvailable?.('Failed to save settings', 'error');
      }
    } else {
      console.log('Settings saved (web mode):', { domain: this.domainValue, explanationStyle: this.explanationStyle });
    }
  }
  async _resetSettings() { 
    this.domainValue = ''; 
    this.explanationStyle = 'detailed';
    this.scrollbarStyle = 'minimal';
    this._applyScrollbarStyle();
    if (window.electronAPI) {
      const result = await window.electronAPI.saveSettings({ domain: '', explanationStyle: 'detailed', scrollbarStyle: 'minimal' });
      if (result.success) {
        this._showNotificationIfAvailable?.('Settings reset successfully', 'success');
      }
    }
  }
  _startSession() { console.warn('UI: _startSession() clicked, but not implemented. Must be overridden in child class.'); }
  _joinSession() { console.warn('UI: _joinSession() clicked, but not implemented. Must be overridden in child class.'); }
  _onManualTermInput(e){ this.manualTerm = e.target.value; }
  _onManualKeyDown(e){ if(e.key === 'Enter'){ e.preventDefault(); this._sendManualRequest(); } }
  _sendManualRequest(){ console.warn('UI: _sendManualRequest() called, but not implemented. Must be overridden in child class.'); }
  _showNotificationIfAvailable(message, type) { console.log(`Notification (${type}): ${message}`); } // Override in child class
  async _loadDomainSettings() { 
    if (window.electronAPI) {
      try {
        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings) {
          if (result.settings.domain) {
            this.domainValue = result.settings.domain;
          }
          if (result.settings.explanationStyle) {
            this.explanationStyle = result.settings.explanationStyle;
          }
          if (result.settings.scrollbarStyle) {
            this.scrollbarStyle = result.settings.scrollbarStyle;
          }
          console.log('Settings loaded:', { domain: this.domainValue, explanationStyle: this.explanationStyle, scrollbarStyle: this.scrollbarStyle });
          this._applyScrollbarStyle();
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      }
    }
  }
  
  _applyScrollbarStyle() {
    // Remove existing scrollbar style classes
    const root = document.documentElement;
    root.classList.remove('scrollbar-minimal', 'scrollbar-glassy', 'scrollbar-hidden', 'scrollbar-default');
    
    // Apply the selected scrollbar style
    if (this.scrollbarStyle) {
      root.classList.add(`scrollbar-${this.scrollbarStyle}`);
    }
  }
  _handlePin(id) { explanationManager.pinExplanation(id); }
  _handleDelete(id) { explanationManager.deleteExplanation(id); }
  _handleCopy(explanation) { const textToCopy = `**${explanation.title}**\n\n${explanation.content}`; navigator.clipboard.writeText(textToCopy); }
  _handleRegenerate(explanation) { console.warn('UI: _handleRegenerate() called, but not implemented. Must be overridden in child class.'); }
  _clearAllExplanations() { if (confirm('Are you sure you want to clear all explanations?')) { explanationManager.clearAll(); } }
  _addTestExplanation() {
    const rand = Math.random() * 0.6 + 0.2; // 0.2 - 0.8 for variety
    explanationManager.addExplanation('Test', 'This is a test explanation.', Date.now(), rand);
  }
  // Window control handlers
  async _winMinimize() { try { await window.electronAPI?.windowControls?.minimize(); } catch (e) { } }
  async _winToggleMaximize() {
    try {
      const isMax = await window.electronAPI?.windowControls?.isMaximized?.();
      if (isMax) await window.electronAPI?.windowControls?.unmaximize();
      else await window.electronAPI?.windowControls?.maximize();
    } catch (e) { }
  }
  async _winClose() { try { await window.electronAPI?.windowControls?.close(); } catch (e) { } }

  updated(changedProperties) {
    super.updated?.(changedProperties);
    
    // Force sync the switch state when isDarkMode changes
    if (changedProperties.has('isDarkMode')) {
      const switchEl = this.shadowRoot?.querySelector('md-switch');
      if (switchEl) {
        switchEl.selected = this.isDarkMode === true;
      }
    }
  }
  async firstUpdated(changed) {
    // Load domain settings
    await this._loadDomainSettings();
    // Load theme preference
    await this._loadThemePreference();
    // Plattform prüfen (nur Windows)
    try {
      this.isWindows = (window.electronAPI?.platform === 'win32');
      // Hole Details, ob frameless aktiv ist
      const plat = await window.electronAPI?.getPlatform?.();
      if (plat && typeof plat.frameless === 'boolean') {
        this.isWindows = this.isWindows && plat.frameless;
      }
    } catch (_) { }
    this.requestUpdate();
    // Reagiere auf Maximierungsstatus, um Icon zu wechseln
    const iconEl = () => this.renderRoot?.querySelector?.('#maximize-icon');
    window.electronAPI?.windowControls?.onMaximized?.(() => { const el = iconEl(); if (el) el.textContent = 'filter_none'; });
    window.electronAPI?.windowControls?.onUnmaximized?.(() => { const el = iconEl(); if (el) el.textContent = 'crop_square'; });
    // Initialen Zustand setzen
    window.electronAPI?.windowControls?.isMaximized?.().then(isMax => {
      const el = iconEl(); if (el) el.textContent = isMax ? 'filter_none' : 'crop_square';
    }).catch(() => { });
  }

  async _loadThemePreference() {
    try {
      if (window.electronAPI?.loadSettings) {
        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings?.theme) {
          this.isDarkMode = result.settings.theme === 'dark' ? true : 
                           result.settings.theme === 'light' ? false : null;
          this._applyTheme();
        }
      }
    } catch (error) {
      console.warn('Failed to load theme preference:', error);
    }
  }

  async _saveThemePreference() {
    try {
      if (window.electronAPI?.saveSettings) {
        const theme = this.isDarkMode === null ? 'system' : 
                     this.isDarkMode ? 'dark' : 'light';
        await window.electronAPI.saveSettings({ theme });
      }
    } catch (error) {
      console.warn('Failed to save theme preference:', error);
    }
  }

  _onThemeToggle(event) {
    // Prevent the switch's default toggle behavior
    event.preventDefault();
    event.stopPropagation();
    
    // Cycle through: system -> light -> dark -> system
    if (this.isDarkMode === null) {
      this.isDarkMode = false; // light
    } else if (this.isDarkMode === false) {
      this.isDarkMode = true; // dark
    } else {
      this.isDarkMode = null; // system
    }
    this._applyTheme();
    this._saveThemePreference();
    
    // Force update the switch state to match our logic
    this.requestUpdate();
  }

  _applyTheme() {
    const root = document.documentElement;
    root.classList.remove('force-light', 'force-dark');
    
    if (this.isDarkMode === true) {
      root.classList.add('force-dark');
    } else if (this.isDarkMode === false) {
      root.classList.add('force-light');
    }
    // If null, use system preference (no classes needed)
  }

  static styles = [sharedStyles, css`
    /* Custom Titlebar */
    .titlebar { height: 32px; display: flex; align-items: center; justify-content: flex-end; background: var(--md-sys-color-surface-variant); border-bottom: 1px solid var(--md-sys-color-outline-variant); position: sticky; top: 0; z-index: 100; -webkit-app-region: drag; }
    .window-controls { display: flex; gap: 4px; padding-right: 6px; -webkit-app-region: no-drag; }
    .win-btn { width: 36px; height: 24px; display:flex; align-items:center; justify-content:center; border:none; background: transparent; color: var(--md-sys-color-on-surface); border-radius: 4px; cursor: pointer; }
    .win-btn:hover { background: var(--md-sys-color-outline-variant); }
    .win-btn.close:hover { background: #ef4444; color: white; }
    /* Session controls layout */
    .session-controls {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 24px;
      border-top: 1px solid var(--md-sys-color-outline-variant);
      padding-top: 24px;
      flex-wrap: wrap; /* Kleine Fenster -> umbrechen statt überlaufen */
    }
    .session-controls md-outlined-text-field {
      flex: 1 1 220px; /* füllt den verfügbaren Platz */
      min-width: 180px;
      width: auto; /* überschreibt globales width:100% */
      margin: 0; /* Ausrichtung in der Zeile */
      order: 1; /* Place input field first */
    }
    .session-controls md-filled-button {
      flex: 0 0 auto;
      white-space: nowrap; /* Button-Text nicht umbrechen */
      order: 2; /* Place "Session erstellen" second */
    }
    .session-controls md-outlined-button {
      flex: 0 0 auto;
      white-space: nowrap; /* Button-Text nicht umbrechen */
      order: 3; /* Place "Session beitreten" third */
    }
    .dialog-code { color: var(--md-sys-color-primary); font-family: 'Roboto Mono', monospace; letter-spacing: 2px; font-size: 2em; text-align: center; margin-top: 8px; user-select: all; }
    
    * Explanations controls layout */
    .explanations-header { margin-bottom: 12px; }
    .explanations-controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .explanations-controls md-outlined-text-field.manual-term-input { flex: 1 1 280px; min-width: 220px; width: auto; margin: 0; }
    .explanations-controls md-filled-button,
    .explanations-controls md-outlined-button { flex: 0 0 auto; white-space: nowrap; }

    /* Status bar positioning */
    status-bar {
      margin: 16px auto;
      width: 90%;
      max-width: 400px;
      display: block;
    }
    
    /* Add spacing between status bar and tabs */
    md-tabs {
      margin-top: 16px;
    }

    /* Style field */
    .style-field {
      --md-outlined-select-text-field-container-height: 64px;
    }
  ` ];
}