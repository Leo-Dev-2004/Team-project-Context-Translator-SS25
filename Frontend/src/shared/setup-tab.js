import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import '@material/web/button/filled-button.js';
import '@material/web/button/outlined-button.js';
import '@material/web/textfield/outlined-text-field.js';
import '@material/web/select/outlined-select.js';
import '@material/web/select/select-option.js';

export class SetupTab extends LitElement {
  static properties = {
    domainValue: { type: String },
    explanationStyle: { type: String },
    scrollbarStyle: { type: String },
  };

  constructor() {
    super();
    this.domainValue = '';
    this.explanationStyle = 'detailed';
    this.scrollbarStyle = 'minimal';
  }

  render() {
    return html`<div class="tab-panel setup-panel">
      <div class="setup-content">
        <h2 class="headline-medium ocean-accent-text setup-title">Setup Your Translation Context</h2>
        <div class="input-section">
          <h3 class="title-medium section-title">Domain Description</h3>
          <p class="body-medium section-description">Describe your field or context to improve translation accuracy.</p>
          <div class="domain-input-group">
            <md-outlined-text-field 
              label="Your domain or context" 
              .value=${this.domainValue} 
              @input=${this._onDomainInput} 
              class="domain-field" 
              type="textarea" 
              rows="3">
            </md-outlined-text-field>
          </div>
        </div>
        <div class="input-section">
          <h3 class="title-medium section-title">Explanation Style</h3>
          <p class="body-medium section-description">Choose how detailed you want the AI explanations to be.</p>
          <div class="style-input-group">
            <md-outlined-select 
              .value=${this.explanationStyle} 
              @change=${this._onExplanationStyleChange} 
              class="style-field">
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
            <md-outlined-select 
              .value=${this.scrollbarStyle} 
              @change=${this._onScrollbarStyleChange} 
              class="style-field">
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
            <md-filled-button id="start-session-button" @click=${this._startSession}>Create Session</md-filled-button>
            <md-outlined-text-field 
              id="session-code-input" 
              label="Session Code" 
              placeholder="Code eingeben...">
            </md-outlined-text-field>
            <md-outlined-button id="join-session-button" @click=${this._joinSession}>Join Session</md-outlined-button>
          </div>
        </div>
      </div>
    </div>`;
  }

  _onDomainInput(e) { 
    this.domainValue = e.target.value; 
    this.dispatchEvent(new CustomEvent('domain-changed', { detail: { domainValue: this.domainValue } }));
  }

  _onExplanationStyleChange(e) { 
    this.explanationStyle = e.target.value; 
    this.dispatchEvent(new CustomEvent('explanation-style-changed', { detail: { explanationStyle: this.explanationStyle } }));
  }

  _onScrollbarStyleChange(e) { 
    this.scrollbarStyle = e.target.value; 
    this.dispatchEvent(new CustomEvent('scrollbar-style-changed', { detail: { scrollbarStyle: this.scrollbarStyle } }));
  }

  async _saveSettings() { 
    this.dispatchEvent(new CustomEvent('save-settings', { 
      detail: { 
        domain: this.domainValue,
        explanationStyle: this.explanationStyle,
        scrollbarStyle: this.scrollbarStyle
      } 
    }));
  }

  async _resetSettings() { 
    this.domainValue = ''; 
    this.explanationStyle = 'detailed';
    this.scrollbarStyle = 'minimal';
    this.dispatchEvent(new CustomEvent('reset-settings'));
  }

  _startSession() { 
    this.dispatchEvent(new CustomEvent('start-session'));
  }

  _joinSession() { 
    const sessionCodeInput = this.shadowRoot.querySelector('#session-code-input');
    const sessionCode = sessionCodeInput?.value || '';
    this.dispatchEvent(new CustomEvent('join-session', { detail: { sessionCode } }));
  }

  static styles = [sharedStyles, css`
    /* Session controls layout */
    .session-controls {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 24px;
      border-top: 1px solid var(--md-sys-color-outline-variant);
      padding-top: 24px;
      flex-wrap: wrap; /* Small windows -> wrap instead of overflow */
    }
    
    .session-controls md-outlined-text-field {
      flex: 1 1 220px; /* fills available space */
      min-width: 180px;
      width: auto; /* overrides global width:100% */
      margin: 0; /* alignment in row */
    }
    
    .session-controls md-filled-button,
    .session-controls md-outlined-button {
      flex: 0 0 auto;
      white-space: nowrap; /* button text no wrap */
    }

    /* Style field */
    .style-field {
      --md-outlined-select-text-field-container-height: 64px;
    }
  `];
}

customElements.define('setup-tab', SetupTab);