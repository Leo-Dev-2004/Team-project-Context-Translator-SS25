import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import './explanation-item.js';
import './chat-box.js';
import '@material/web/textfield/outlined-text-field.js';
import '@material/web/iconbutton/icon-button.js';
import '@material/web/button/outlined-button.js';

export class ExplanationsTab extends LitElement {
  static properties = {
    explanations: { type: Array },
    manualTerm: { type: String },
    isConnected: { type: Boolean }
  };

  constructor() {
    super();
    this.explanations = [];
    this.manualTerm = '';
    this.isConnected = false;
  }

  render() {
    return html`<div class="tab-panel explanations-panel">
      <div class="explanations-header">
        <h2 class="headline-medium ocean-accent-text">AI Explanations</h2>
        <div class="explanations-controls">
          <md-outlined-text-field 
            id="manual-term-input" 
            class="manual-term-input" 
            label="Explain a term" 
            placeholder="e.g. OAuth, ROI, Kafka" 
            .value=${this.manualTerm} 
            @input=${this._onManualTermInput} 
            @keydown=${this._onManualKeyDown}>
            <md-icon-button 
              id="manual-send-button" 
              slot="trailing-icon" 
              class="accent" 
              title="Send" 
              aria-label="Send" 
              @click=${this._sendManualRequest} 
              ?disabled=${!(this.manualTerm && this.manualTerm.trim())}>
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
        ${this.explanations.length === 0 ? 
          html`<div class="empty-state">
            <p>No explanations yet. Ask for an explanation or wait for one to be generated.</p>
          </div>` : 
          html`<div class="explanations-list">
            ${this.explanations.map(explanation => 
              html`<explanation-item 
                .explanation=${explanation} 
                .onPin=${this._handlePin.bind(this)} 
                .onDelete=${this._handleDelete.bind(this)} 
                .onCopy=${this._handleCopy.bind(this)} 
                .onRegenerate=${this._handleRegenerate.bind(this)}>
              </explanation-item>`
            )}
          </div>`
        }
      </div>

      <chat-box 
        .isConnected=${this.isConnected}
        @send-chat-message=${this._handleChatMessage}
        @clear-chat=${this._handleClearChat}>
      </chat-box>
    </div>`;
  }

  _onManualTermInput(e) { 
    this.manualTerm = e.target.value; 
    this.dispatchEvent(new CustomEvent('manual-term-changed', { detail: { manualTerm: this.manualTerm } }));
  }

  _onManualKeyDown(e) { 
    if (e.key === 'Enter') { 
      e.preventDefault(); 
      this._sendManualRequest(); 
    } 
  }

  _sendManualRequest() { 
    if (this.manualTerm && this.manualTerm.trim()) {
      this.dispatchEvent(new CustomEvent('send-manual-request', { detail: { term: this.manualTerm.trim() } }));
      this.manualTerm = '';
    }
  }

  _clearAllExplanations() { 
    this.dispatchEvent(new CustomEvent('clear-all-explanations'));
  }

  _handlePin(id) { 
    this.dispatchEvent(new CustomEvent('pin-explanation', { detail: { id } }));
  }

  _handleDelete(id) { 
    this.dispatchEvent(new CustomEvent('delete-explanation', { detail: { id } }));
  }

  _handleCopy(explanation) { 
    this.dispatchEvent(new CustomEvent('copy-explanation', { detail: { explanation } }));
  }

  _handleRegenerate(explanation) { 
    this.dispatchEvent(new CustomEvent('regenerate-explanation', { detail: { explanation } }));
  }

  _handleChatMessage(e) {
    this.dispatchEvent(new CustomEvent('send-chat-message', { detail: e.detail }));
  }

  _handleClearChat(e) {
    this.dispatchEvent(new CustomEvent('clear-chat', { detail: e.detail }));
  }

  // Method to forward chat messages to the chat box
  addChatMessage(content, type = 'assistant') {
    const chatBox = this.shadowRoot.querySelector('chat-box');
    if (chatBox) {
      chatBox.addMessage(content, type);
    }
  }

  // Method to update chat connection status
  setChatConnectionStatus(isConnected) {
    this.isConnected = isConnected;
    const chatBox = this.shadowRoot.querySelector('chat-box');
    if (chatBox) {
      chatBox.setConnectionStatus(isConnected);
    }
  }

  // Method to set chat loading state
  setChatLoading(isLoading) {
    const chatBox = this.shadowRoot.querySelector('chat-box');
    if (chatBox) {
      chatBox.setLoading(isLoading);
    }
  }

  static styles = [sharedStyles, css`
    /* Explanations controls layout */
    .explanations-header { 
      margin-bottom: 12px; 
    }
    
    .explanations-controls { 
      display: flex; 
      align-items: center; 
      gap: 12px; 
      flex-wrap: wrap; 
    }
    
    .explanations-controls md-outlined-text-field.manual-term-input { 
      flex: 1 1 280px; 
      min-width: 220px; 
      width: auto; 
      margin: 0; 
    }
    
    .explanations-controls md-filled-button,
    .explanations-controls md-outlined-button { 
      flex: 0 0 auto; 
      white-space: nowrap; 
    }

    .explanations-content {
      margin-bottom: 16px;
    }

    .empty-state {
      text-align: center;
      color: var(--md-sys-color-on-surface-variant);
      padding: 48px 24px;
      font-style: italic;
    }

    .explanations-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
  `];
}

customElements.define('explanations-tab', ExplanationsTab);