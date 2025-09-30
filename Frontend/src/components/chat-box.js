import { LitElement, css, html } from 'lit';
import { sharedStyles } from './styles.js';
import '@material/web/textfield/outlined-text-field.js';
import '@material/web/iconbutton/icon-button.js';
import '@material/web/button/outlined-button.js';

export class ChatBox extends LitElement {
  static properties = {
    message: { type: String },
    isConnected: { type: Boolean },
    isLoading: { type: Boolean },
    messages: { type: Array }
  };

  constructor() {
    super();
    this.message = '';
    this.isConnected = false;
    this.isLoading = false;
    this.messages = [];
  }

  render() {
    return html`<div class="chat-box">
      <div class="chat-header">
        <h3 class="title-medium">Direct Chat with AI</h3>
        <div class="connection-status ${this.isConnected ? 'connected' : 'disconnected'}">
          <div class="status-indicator"></div>
          <span>${this.isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>
      
      <div class="chat-messages" id="chat-messages">
        ${this.messages.length === 0 ? 
          html`<div class="empty-chat">
            <p>Start a conversation with the AI assistant. Ask questions about terms, concepts, or request explanations.</p>
          </div>` :
          this.messages.map(msg => html`
            <div class="message ${msg.type}">
              <div class="message-content">
                <div class="message-text">${msg.content}</div>
                <div class="message-time">${this._formatTime(msg.timestamp)}</div>
              </div>
            </div>
          `)
        }
        ${this.isLoading ? html`<div class="message assistant loading">
          <div class="message-content">
            <div class="loading-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>` : ''}
      </div>

      <div class="chat-input">
        <md-outlined-text-field
          id="chat-input-field"
          label="Ask the AI..."
          placeholder="e.g., What is OAuth? Explain microservices architecture"
          .value=${this.message}
          @input=${this._onMessageInput}
          @keydown=${this._onKeyDown}
          class="message-input"
          type="textarea"
          rows="2">
          <md-icon-button 
            slot="trailing-icon" 
            class="send-button" 
            title="Send message" 
            aria-label="Send message" 
            @click=${this._sendMessage}
            ?disabled=${!this.message.trim() || !this.isConnected || this.isLoading}>
            <span class="material-icons">send</span>
          </md-icon-button>
        </md-outlined-text-field>
        <div class="chat-controls">
          <md-outlined-button @click=${this._clearChat} ?disabled=${this.messages.length === 0}>
            <span class="material-icons" slot="icon">clear</span>
            Clear Chat
          </md-outlined-button>
        </div>
      </div>
    </div>`;
  }

  _onMessageInput(e) {
    this.message = e.target.value;
  }

  _onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this._sendMessage();
    }
  }

  _sendMessage() {
    if (!this.message.trim() || !this.isConnected || this.isLoading) return;

    const userMessage = {
      type: 'user',
      content: this.message.trim(),
      timestamp: Date.now()
    };

    this.messages = [...this.messages, userMessage];
    this.isLoading = true;

    // Dispatch event to parent to handle actual sending
    this.dispatchEvent(new CustomEvent('send-chat-message', { 
      detail: { message: userMessage.content }
    }));

    this.message = '';
    this._scrollToBottom();
  }

  _clearChat() {
    this.messages = [];
    this.dispatchEvent(new CustomEvent('clear-chat'));
  }

  _formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  }

  _scrollToBottom() {
    this.updateComplete.then(() => {
      const messagesContainer = this.shadowRoot.querySelector('#chat-messages');
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    });
  }

  // Method to add AI response from parent component
  addMessage(content, type = 'assistant') {
    const message = {
      type,
      content,
      timestamp: Date.now()
    };
    this.messages = [...this.messages, message];
    this.isLoading = false;
    this._scrollToBottom();
  }

  // Method to update connection status
  setConnectionStatus(isConnected) {
    this.isConnected = isConnected;
  }

  // Method to set loading state
  setLoading(isLoading) {
    this.isLoading = isLoading;
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    if (changedProperties.has('messages')) {
      this._scrollToBottom();
    }
  }

  static styles = [sharedStyles, css`
    .chat-box {
      border: 1px solid var(--md-sys-color-outline-variant);
      border-radius: 12px;
      background: var(--md-sys-color-surface);
      margin-top: 16px;
      display: flex;
      flex-direction: column;
      height: 400px;
      overflow: hidden;
    }

    .chat-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--md-sys-color-outline-variant);
      background: var(--md-sys-color-surface-variant);
    }

    .connection-status {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .connection-status.connected .status-indicator {
      background: #4caf50;
    }

    .connection-status.disconnected .status-indicator {
      background: #f44336;
    }

    .chat-messages {
      flex: 1;
      padding: 12px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .empty-chat {
      text-align: center;
      color: var(--md-sys-color-on-surface-variant);
      padding: 24px;
      font-style: italic;
    }

    .message {
      display: flex;
      max-width: 85%;
    }

    .message.user {
      align-self: flex-end;
    }

    .message.assistant {
      align-self: flex-start;
    }

    .message-content {
      padding: 8px 12px;
      border-radius: 16px;
      background: var(--md-sys-color-surface-variant);
      position: relative;
    }

    .message.user .message-content {
      background: var(--md-sys-color-primary);
      color: var(--md-sys-color-on-primary);
    }

    .message-text {
      margin-bottom: 4px;
      line-height: 1.4;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .message-time {
      font-size: 11px;
      opacity: 0.7;
      text-align: right;
    }

    .message.user .message-time {
      color: var(--md-sys-color-on-primary);
    }

    .loading-indicator {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .loading-indicator span {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--md-sys-color-on-surface-variant);
      animation: bounce 1.4s infinite ease-in-out both;
    }

    .loading-indicator span:nth-child(1) { animation-delay: -0.32s; }
    .loading-indicator span:nth-child(2) { animation-delay: -0.16s; }

    @keyframes bounce {
      0%, 80%, 100% { 
        transform: scale(0);
      } 40% { 
        transform: scale(1);
      }
    }

    .chat-input {
      padding: 12px;
      border-top: 1px solid var(--md-sys-color-outline-variant);
      background: var(--md-sys-color-surface-variant);
    }

    .message-input {
      width: 100%;
      margin-bottom: 8px;
    }

    .send-button {
      color: var(--md-sys-color-primary);
    }

    .send-button:disabled {
      color: var(--md-sys-color-on-surface-variant);
      opacity: 0.5;
    }

    .chat-controls {
      display: flex;
      justify-content: flex-end;
    }

    /* Custom scrollbar for chat messages */
    .chat-messages::-webkit-scrollbar {
      width: 6px;
    }

    .chat-messages::-webkit-scrollbar-track {
      background: transparent;
    }

    .chat-messages::-webkit-scrollbar-thumb {
      background: var(--md-sys-color-outline-variant);
      border-radius: 3px;
    }

    .chat-messages::-webkit-scrollbar-thumb:hover {
      background: var(--md-sys-color-outline);
    }
  `];
}

customElements.define('chat-box', ChatBox);