import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import './status-bar.js';
import '@material/web/tabs/tabs.js';
import '@material/web/tabs/primary-tab.js';
import '@material/web/dialog/dialog.js';
import '@material/web/switch/switch.js';
import '@material/web/button/text-button.js';

export class MainBody extends LitElement {
  static properties = {
    activeTab: { type: Number },
    isWindows: { type: Boolean },
    serverStatus: { type: String },
    microphoneStatus: { type: String },
    isDarkMode: { type: Boolean },
    sessionCode: { type: String },
  };

  constructor() {
    super();
    this.activeTab = 0;
    this.isWindows = false;
    this.serverStatus = 'initializing';
    this.microphoneStatus = 'initializing';
    this.isDarkMode = null;
    this.sessionCode = '';
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
          <h2 id="dialog-session-code" class="dialog-code">${this.sessionCode}</h2>
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
        <div class="tab-content">
          <slot name="tab-content"></slot>
        </div>
      </div>
    </div>`;
  }

  _onTabChange(e) {
    this.activeTab = e.target.activeTabIndex;
    this.dispatchEvent(new CustomEvent('tab-changed', { detail: { activeTab: this.activeTab } }));
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
    
    this.dispatchEvent(new CustomEvent('theme-changed', { detail: { isDarkMode: this.isDarkMode } }));
    
    // Force update the switch state to match our logic
    this.requestUpdate();
  }

  // Window control handlers
  async _winMinimize() { 
    try { 
      await window.electronAPI?.windowControls?.minimize(); 
    } catch (e) { } 
  }

  async _winToggleMaximize() {
    try {
      const isMax = await window.electronAPI?.windowControls?.isMaximized?.();
      if (isMax) await window.electronAPI?.windowControls?.unmaximize();
      else await window.electronAPI?.windowControls?.maximize();
    } catch (e) { }
  }

  async _winClose() { 
    try { 
      await window.electronAPI?.windowControls?.close(); 
    } catch (e) { } 
  }

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

  firstUpdated() {
    // Platform check (Windows only)
    try {
      this.isWindows = (window.electronAPI?.platform === 'win32');
      // Check if frameless is active
      window.electronAPI?.getPlatform?.().then(plat => {
        if (plat && typeof plat.frameless === 'boolean') {
          this.isWindows = this.isWindows && plat.frameless;
          this.requestUpdate();
        }
      });
    } catch (_) { }

    // React to maximization status to change icon
    const iconEl = () => this.renderRoot?.querySelector?.('#maximize-icon');
    window.electronAPI?.windowControls?.onMaximized?.(() => { 
      const el = iconEl(); 
      if (el) el.textContent = 'filter_none'; 
    });
    window.electronAPI?.windowControls?.onUnmaximized?.(() => { 
      const el = iconEl(); 
      if (el) el.textContent = 'crop_square'; 
    });
    
    // Set initial state
    window.electronAPI?.windowControls?.isMaximized?.().then(isMax => {
      const el = iconEl(); 
      if (el) el.textContent = isMax ? 'filter_none' : 'crop_square';
    }).catch(() => { });
  }

  static styles = [sharedStyles, css`
    /* Custom Titlebar */
    .titlebar { 
      height: 32px; 
      display: flex; 
      align-items: center; 
      justify-content: flex-end; 
      background: var(--md-sys-color-surface-variant); 
      border-bottom: 1px solid var(--md-sys-color-outline-variant); 
      position: sticky; 
      top: 0; 
      z-index: 100; 
      -webkit-app-region: drag; 
    }
    
    .window-controls { 
      display: flex; 
      gap: 4px; 
      padding-right: 6px; 
      -webkit-app-region: no-drag; 
    }
    
    .win-btn { 
      width: 36px; 
      height: 24px; 
      display: flex; 
      align-items: center; 
      justify-content: center; 
      border: none; 
      background: transparent; 
      color: var(--md-sys-color-on-surface); 
      border-radius: 4px; 
      cursor: pointer; 
    }
    
    .win-btn:hover { 
      background: var(--md-sys-color-outline-variant); 
    }
    
    .win-btn.close:hover { 
      background: #ef4444; 
      color: white; 
    }

    .dialog-code { 
      color: var(--md-sys-color-primary); 
      font-family: 'Roboto Mono', monospace; 
      letter-spacing: 2px; 
      font-size: 2em; 
      text-align: center; 
      margin-top: 8px; 
      user-select: all; 
    }

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
  `];
}

customElements.define('main-body', MainBody);