// Refactored UI component using split components
import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import { explanationManager } from './explanation-manager.js';
import './main-body.js';
import './setup-tab.js';
import './explanations-tab.js';

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
    scrollbarStyle: { type: String },
    sessionCode: { type: String }
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
    this.scrollbarStyle = 'minimal';
    this.sessionCode = '';
    
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
    return html`
      <main-body
        .activeTab=${this.activeTab}
        .isWindows=${this.isWindows}
        .serverStatus=${this.serverStatus}
        .microphoneStatus=${this.microphoneStatus}
        .isDarkMode=${this.isDarkMode}
        .sessionCode=${this.sessionCode}
        @tab-changed=${this._onTabChanged}
        @theme-changed=${this._onThemeChanged}>
        
        <div slot="tab-content">
          ${this._renderTabContent()}
        </div>
      </main-body>
    `;
  }

  _renderTabContent() {
    switch (this.activeTab) {
      case 0:
        return html`
          <setup-tab
            .domainValue=${this.domainValue}
            .explanationStyle=${this.explanationStyle}
            .scrollbarStyle=${this.scrollbarStyle}
            .sessionCode=${this.sessionCode}
            @domain-changed=${this._onDomainChanged}
            @explanation-style-changed=${this._onExplanationStyleChanged}
            @scrollbar-style-changed=${this._onScrollbarStyleChanged}
            @save-settings=${this._onSaveSettings}
            @reset-settings=${this._onResetSettings}
            @start-session=${this._onStartSession}
            @join-session=${this._onJoinSession}>
          </setup-tab>
        `;
      case 1:
        return html`
          <explanations-tab
            .explanations=${this.explanations}
            .manualTerm=${this.manualTerm}
            .isConnected=${this.serverStatus === 'connected'}
            @manual-term-changed=${this._onManualTermChanged}
            @send-manual-request=${this._onSendManualRequest}
            @clear-all-explanations=${this._onClearAllExplanations}
            @pin-explanation=${this._onPinExplanation}
            @delete-explanation=${this._onDeleteExplanation}
            @copy-explanation=${this._onCopyExplanation}
            @regenerate-explanation=${this._onRegenerateExplanation}>
          </explanations-tab>
        `;
      default:
        return html`<div class="tab-panel">Select a tab</div>`;
    }
  }
  // Event handlers for MainBody
  _onTabChanged(e) {
    this.activeTab = e.detail.activeTab;
  }

  _onThemeChanged(e) {
    this.isDarkMode = e.detail.isDarkMode;
    this._applyTheme();
    this._saveThemePreference();
  }

  // Event handlers for SetupTab
  _onDomainChanged(e) {
    this.domainValue = e.detail.domainValue;
  }

  _onExplanationStyleChanged(e) {
    this.explanationStyle = e.detail.explanationStyle;
  }

  _onScrollbarStyleChanged(e) {
    this.scrollbarStyle = e.detail.scrollbarStyle;
    this._applyScrollbarStyle();
  }

  _onSaveSettings(e) {
    this._saveSettings(e.detail);
  }

  _onResetSettings(e) {
    this._resetSettings();
  }

  _onStartSession(e) {
    this._startSession();
  }

  _onJoinSession(e) {
    this._joinSession(e.detail.sessionCode);
  }

  // Event handlers for ExplanationsTab
  _onManualTermChanged(e) {
    this.manualTerm = e.detail.manualTerm;
  }

  _onSendManualRequest(e) {
    this._sendManualRequest(e.detail.term);
  }

  _onClearAllExplanations(e) {
    this._clearAllExplanations();
  }

  _onPinExplanation(e) {
    explanationManager.pinExplanation(e.detail.id);
  }

  _onDeleteExplanation(e) {
    explanationManager.deleteExplanation(e.detail.id);
  }

  _onCopyExplanation(e) {
    this._handleCopy(e.detail.explanation);
  }

  _onRegenerateExplanation(e) {
    this._handleRegenerate(e.detail.explanation);
  }

  // Implementation methods (these should be overridden in child classes)
  async _saveSettings(settings) { 
    if (window.electronAPI) {
      const result = await window.electronAPI.saveSettings(settings);
      if (result.success) {
        console.log('Settings saved successfully:', settings);
        this._showNotificationIfAvailable?.('Settings saved successfully', 'success');
      } else {
        console.error('Failed to save settings:', result.error);
        this._showNotificationIfAvailable?.('Failed to save settings', 'error');
      }
    } else {
      console.log('Settings saved (web mode):', settings);
    }
  }
  async _resetSettings() { 
    this.domainValue = ''; 
    this.explanationStyle = 'detailed';
    this.scrollbarStyle = 'minimal';
    this._applyScrollbarStyle();
    if (window.electronAPI) {
      const result = await window.electronAPI.saveSettings({ 
        domain: '', 
        explanationStyle: 'detailed', 
        scrollbarStyle: 'minimal' 
      });
      if (result.success) {
        this._showNotificationIfAvailable?.('Settings reset successfully', 'success');
      }
    }
    // Update the setup tab
    this.requestUpdate();
  }

  _startSession() { 
    console.warn('UI: _startSession() clicked, but not implemented. Must be overridden in child class.'); 
  }

  _joinSession(sessionCode) { 
    console.warn('UI: _joinSession() clicked, but not implemented. Must be overridden in child class.'); 
  }

  _sendManualRequest(term) { 
    console.warn('UI: _sendManualRequest() called, but not implemented. Must be overridden in child class.'); 
  }

  _clearAllExplanations() { 
    if (confirm('Are you sure you want to clear all explanations?')) { 
      explanationManager.clearAll(); 
    } 
  }

  _handleCopy(explanation) { 
    const textToCopy = `**${explanation.title}**\n\n${explanation.content}`; 
    navigator.clipboard.writeText(textToCopy); 
  }

  _handleRegenerate(explanation) { 
    console.warn('UI: _handleRegenerate() called, but not implemented. Must be overridden in child class.'); 
  }

  _showNotificationIfAvailable(message, type) { 
    console.log(`Notification (${type}): ${message}`); 
  }

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
          console.log('Settings loaded:', { 
            domain: this.domainValue, 
            explanationStyle: this.explanationStyle, 
            scrollbarStyle: this.scrollbarStyle 
          });
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

  async firstUpdated(changed) {
    // Load domain settings
    await this._loadDomainSettings();
    // Load theme preference
    await this._loadThemePreference();
    
    // Platform check (Windows only)
    try {
      this.isWindows = (window.electronAPI?.platform === 'win32');
      // Get details about whether frameless is active
      const plat = await window.electronAPI?.getPlatform?.();
      if (plat && typeof plat.frameless === 'boolean') {
        this.isWindows = this.isWindows && plat.frameless;
      }
    } catch (_) { }
    this.requestUpdate();
  }

  static styles = [sharedStyles];
}