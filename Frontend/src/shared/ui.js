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

export class UI extends LitElement {
  static properties = { activeTab: { type: Number }, domainValue: { type: String }, explanations: { type: Array }, isWindows: { type: Boolean } };
  constructor() { super(); this.activeTab = 0; this.domainValue=''; this.explanations=[]; this.isWindows=false; this._explanationListener=(exps)=>{ this.explanations=[...exps]; }; explanationManager.addListener(this._explanationListener); }
  disconnectedCallback() { super.disconnectedCallback(); explanationManager.removeListener(this._explanationListener); }
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
          <md-text-button @click=${()=>this.shadowRoot.querySelector('#session-dialog').close()}>Close</md-text-button>
        </div>
      </md-dialog>
      <div class="ui-app-container">
        <header class="app-header ocean-header">
          <h1 class="display-medium">Context Translator</h1>
          <p class="body-large">Real-time meeting explanations and summaries powered by AI.</p>
        </header>
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
            <div class="spacer"></div>
            <div class="action-buttons">
              <md-filled-button @click=${this._saveSettings}>Save Configuration</md-filled-button>
              <md-outlined-button @click=${this._resetSettings}>Reset to Defaults</md-outlined-button>
              <div class="session-controls">
                <md-filled-button id="start-session-button" @click=${this._startSession}>Session erstellen</md-filled-button>
                <md-outlined-text-field id="session-code-input" label="Session Code" placeholder="Code eingeben..."></md-outlined-text-field>
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
              <md-text-button @click=${this._clearAllExplanations}><span class="material-icons">delete</span> Clear All</md-text-button>
              <md-filled-button @click=${this._addTestExplanation}><span class="material-icons">add</span> Add Test</md-filled-button>
            </div>
          </div>
          <div class="explanations-content">
            ${this.explanations.length===0 ? html`<div class="empty-state"><p>No explanations yet.</p></div>` : html`<div class="explanations-list">
              ${this.explanations.map(explanation => html`<explanation-item .explanation=${explanation} .onPin=${this._handlePin.bind(this)} .onDelete=${this._handleDelete.bind(this)} .onCopy=${this._handleCopy.bind(this)}></explanation-item>`)}
            </div>`}
          </div>
        </div>`;
      default:
        return html`<div class="tab-panel">Select a tab</div>`;
    }
  }
  _onTabChange(e){ this.activeTab = e.target.activeTabIndex; }
  _onDomainInput(e){ this.domainValue = e.target.value; }
  _saveSettings(){ console.log('Settings saved:', { domain: this.domainValue }); }
  _resetSettings(){ this.domainValue=''; }
  _startSession(){ console.warn('UI: _startSession() clicked, but not implemented. Must be overridden in child class.'); }
  _joinSession(){ console.warn('UI: _joinSession() clicked, but not implemented. Must be overridden in child class.'); }
  _handlePin(id){ explanationManager.pinExplanation(id); }
  _handleDelete(id){ explanationManager.deleteExplanation(id); }
  _handleCopy(explanation){ const textToCopy = `**${explanation.title}**\n\n${explanation.content}`; navigator.clipboard.writeText(textToCopy); }
  _clearAllExplanations(){ if (confirm('Are you sure you want to clear all explanations?')) { explanationManager.clearAll(); } }
  _addTestExplanation(){ explanationManager.addExplanation('Test','This is a test explanation.'); }
  // Window control handlers
  async _winMinimize(){ try{ await window.electronAPI?.windowControls?.minimize(); }catch(e){} }
  async _winToggleMaximize(){
    try{
      const isMax = await window.electronAPI?.windowControls?.isMaximized?.();
      if (isMax) await window.electronAPI?.windowControls?.unmaximize();
      else await window.electronAPI?.windowControls?.maximize();
    }catch(e){}
  }
  async _winClose(){ try{ await window.electronAPI?.windowControls?.close(); }catch(e){} }

  async firstUpdated(changed){
    super.firstUpdated?.(changed);
    // Plattform prüfen (nur Windows)
    try{
      this.isWindows = (window.electronAPI?.platform === 'win32');
      // Hole Details, ob frameless aktiv ist
      const plat = await window.electronAPI?.getPlatform?.();
      if (plat && typeof plat.frameless === 'boolean') {
        this.isWindows = this.isWindows && plat.frameless;
      }
    }catch(_){}
    this.requestUpdate();
    // Reagiere auf Maximierungsstatus, um Icon zu wechseln
    const iconEl = () => this.renderRoot?.querySelector?.('#maximize-icon');
    window.electronAPI?.windowControls?.onMaximized?.(() => { const el = iconEl(); if (el) el.textContent = 'filter_none'; });
    window.electronAPI?.windowControls?.onUnmaximized?.(() => { const el = iconEl(); if (el) el.textContent = 'crop_square'; });
    // Initialen Zustand setzen
    window.electronAPI?.windowControls?.isMaximized?.().then(isMax => {
      const el = iconEl(); if (el) el.textContent = isMax ? 'filter_none' : 'crop_square';
    }).catch(()=>{});
  }

  static styles = [ sharedStyles, css`
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
    }
    .session-controls md-filled-button,
    .session-controls md-outlined-button {
      flex: 0 0 auto;
      white-space: nowrap; /* Button-Text nicht umbrechen */
    }
    .dialog-code { color: var(--md-sys-color-primary); font-family: 'Roboto Mono', monospace; letter-spacing: 2px; font-size: 2em; text-align: center; margin-top: 8px; user-select: all; }
  ` ];
}
