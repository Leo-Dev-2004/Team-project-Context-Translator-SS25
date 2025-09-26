// flattened copy from shared/src/explanation-item.js
import { LitElement, html } from 'lit';
import { marked } from 'marked';
import { sharedStyles } from './styles.js';

export class ExplanationItem extends LitElement {
  static properties = {
    explanation: { type: Object },
    expanded: { type: Boolean },
    onPin: { type: Function },
    onDelete: { type: Function },
    onCopy: { type: Function },
    onRegenerate: { type: Function }
  };
  static styles = [sharedStyles];
  constructor() { super(); this.expanded = false; this.explanation = {}; }
  render() {
    if (this.explanation.isDeleted) return html``;
    return html`
      <div class="explanation-card ${this.explanation.isPinned ? 'pinned' : ''}">
        <div class="explanation-header" @click=${this._toggleExpanded}>
          <div class="explanation-title">
            ${this.explanation.isPinned ? html`<span class="pinned-indicator material-icons">push_pin</span>` : ''}
            ${this.explanation.title}
            ${this._renderConfidenceBadge(this.explanation.confidence)}
          </div>
          <div class="explanation-actions" @click=${this._stopPropagation}>
            <button class="action-button pin-button ${this.explanation.isPinned ? 'pinned' : ''}" @click=${this._handlePin} title="${this.explanation.isPinned ? 'Unpin' : 'Pin'} explanation">
              <span class="material-icons">${this.explanation.isPinned ? 'push_pin' : 'push_pin'}</span>
            </button>
            <button class="action-button delete-button" @click=${this._handleDelete} title="Delete explanation">
              <span class="material-icons">close</span>
            </button>
          </div>
          <div class="expand-icon ${this.expanded ? 'expanded' : ''}" title="Toggle explanation">
            <span class="material-icons">expand_more</span>
          </div>
        </div>
        <div class="explanation-content ${this.expanded ? 'expanded' : ''}">
          <div class="explanation-body">
            <div class="explanation-text markdown-content">
              ${this._renderMarkdown(this.explanation.content)}
            </div>
            <div class="explanation-footer">
              <span class="explanation-timestamp">${this._formatTimestamp(this.explanation.timestamp)}</span>
              <div class="footer-actions">
                <button class="regenerate-button" @click=${this._handleRegenerate} title="Regenerate explanation">
                  <span class="material-icons">refresh</span> Regenerate
                </button>
                <button class="copy-button" @click=${this._handleCopy} title="Copy explanation">
                  <span class="material-icons">content_copy</span> Copy
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
  }
  _toggleExpanded() { this.expanded = !this.expanded; }
  _stopPropagation(e) { e.stopPropagation(); }
  _handlePin(e) { e.stopPropagation(); if (this.onPin) this.onPin(this.explanation.id); }
  _handleDelete(e) { e.stopPropagation(); if (this.onDelete) this.onDelete(this.explanation.id); }
  _handleCopy() { if (this.onCopy) this.onCopy(this.explanation); }
  _handleRegenerate(e) { e.stopPropagation(); if (this.onRegenerate) this.onRegenerate(this.explanation); }
  _renderMarkdown(content) {
    if (!content) return html``;
    
    // Check if this is a processing/loading state
    if (content.includes('🔄 Generating explanation')) {
      return html`
        <div class="processing-content">
          <div class="processing-indicator">
            <div class="spinner"></div>
            <span>Generating explanation...</span>
          </div>
          <div class="processing-details">${content.replace('🔄 Generating explanation for', 'Analyzing term:').replace('...', '')}</div>
        </div>
      `;
    }
    
    try {
      marked.setOptions({ breaks: true, gfm: true, sanitize: false, smartLists: true, smartypants: false });
      const htmlContent = marked.parse(content);
      return html`<div .innerHTML=${htmlContent}></div>`;
    } catch (error) {
      console.error('Markdown parsing error:', error);
      const processedContent = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
      return html`<div .innerHTML=${processedContent}></div>`;
    }
  }
  _formatTimestamp(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  _renderConfidenceBadge(confidence) {
    if (typeof confidence !== 'number' || !isFinite(confidence)) return html``;
    const clamped = Math.max(0, Math.min(1, confidence));
    const pct = Math.round(clamped * 100);
    const level = this._confidenceLevel(pct);
    return html`<span class="confidence-badge ${level}" title="Confidence: ${pct}%">${pct}%</span>`;
  }

  _confidenceLevel(percent) {
    if (percent >= 75) return 'high';
    if (percent >= 50) return 'medium';
    return 'low';
  }
}
customElements.define('explanation-item', ExplanationItem);
