import { LitElement, html, css } from 'lit';

export class ExplanationItem extends LitElement {
  static properties = {
    explanation: { type: Object },
    expanded: { type: Boolean },
    onPin: { type: Function },
    onDelete: { type: Function },
    onCopy: { type: Function }
  };

  static styles = css`
    :host {
      display: block;
      margin-bottom: 12px;
    }

    .explanation-card {
      background: var(--md-sys-color-surface-container-lowest);
      border: 1px solid var(--md-sys-color-outline-variant);
      border-radius: 12px;
      overflow: hidden;
      transition: all 0.3s ease;
    }

    .explanation-card.pinned {
      background: var(--md-sys-color-secondary-container);
      border-color: var(--md-sys-color-secondary);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .explanation-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px;
      cursor: pointer;
      transition: background-color 0.2s ease;
    }

    .explanation-header:hover {
      background: var(--md-sys-color-surface-container);
    }

    .explanation-title {
      font-family: var(--md-sys-typescale-title-medium-font);
      font-size: var(--md-sys-typescale-title-medium-size);
      font-weight: var(--md-sys-typescale-title-medium-weight);
      color: var(--md-sys-color-on-surface);
      flex: 1;
      margin-right: 16px;
    }

    .explanation-actions {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .expand-icon {
      transition: transform 0.3s ease;
    }

    .expand-icon.expanded {
      transform: rotate(180deg);
    }

    .explanation-content {
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.3s ease;
    }

    .explanation-content.expanded {
      max-height: 1000px;
    }

    .explanation-body {
      padding: 0 16px 16px 16px;
    }

    .explanation-text {
      background: var(--md-sys-color-surface-container);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 12px;
      font-family: var(--md-sys-typescale-body-medium-font);
      font-size: var(--md-sys-typescale-body-medium-size);
      line-height: 1.6;
      color: var(--md-sys-color-on-surface);
      white-space: pre-wrap;
    }

    .explanation-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 8px;
      border-top: 1px solid var(--md-sys-color-outline-variant);
    }

    .explanation-timestamp {
      font-family: var(--md-sys-typescale-body-small-font);
      font-size: var(--md-sys-typescale-body-small-size);
      color: var(--md-sys-color-on-surface-variant);
    }

    .pinned-indicator {
      color: var(--md-sys-color-secondary);
    }

    .deleted {
      opacity: 0.5;
      pointer-events: none;
    }
  `;

  constructor() {
    super();
    this.expanded = false;
    this.explanation = {};
  }

  render() {
    if (this.explanation.isDeleted) {
      return html``;
    }

    return html`
      <div class="explanation-card ${this.explanation.isPinned ? 'pinned' : ''}">
        <div class="explanation-header" @click=${this._toggleExpanded}>
          <div class="explanation-title">
            ${this.explanation.isPinned ? html`<md-icon class="pinned-indicator">push_pin</md-icon> ` : ''}
            ${this.explanation.title}
          </div>
          <div class="explanation-actions" @click=${this._stopPropagation}>
            <md-icon-button @click=${this._handlePin}>
              <md-icon>${this.explanation.isPinned ? 'push_pin' : 'push_pin_outlined'}</md-icon>
            </md-icon-button>
            <md-icon-button @click=${this._handleDelete}>
              <md-icon>delete</md-icon>
            </md-icon-button>
          </div>
          <md-icon class="expand-icon ${this.expanded ? 'expanded' : ''}">
            expand_more
          </md-icon>
        </div>
        
        <div class="explanation-content ${this.expanded ? 'expanded' : ''}">
          <div class="explanation-body">
            <div class="explanation-text">
              ${this._renderMarkdown(this.explanation.content)}
            </div>
            <div class="explanation-footer">
              <span class="explanation-timestamp">
                ${this._formatTimestamp(this.explanation.timestamp)}
              </span>
              <md-text-button @click=${this._handleCopy}>
                <md-icon slot="icon">content_copy</md-icon>
                Copy
              </md-text-button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _toggleExpanded() {
    this.expanded = !this.expanded;
  }

  _stopPropagation(e) {
    e.stopPropagation();
  }

  _handlePin(e) {
    e.stopPropagation();
    if (this.onPin) {
      this.onPin(this.explanation.id);
    }
  }

  _handleDelete(e) {
    e.stopPropagation();
    if (this.onDelete) {
      this.onDelete(this.explanation.id);
    }
  }

  _handleCopy() {
    if (this.onCopy) {
      this.onCopy(this.explanation);
    }
  }

  _renderMarkdown(content) {
    // Einfache Markdown-Unterstützung (erweiterbar)
    if (!content) return '';
    
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  _formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    return date.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
}

customElements.define('explanation-item', ExplanationItem);