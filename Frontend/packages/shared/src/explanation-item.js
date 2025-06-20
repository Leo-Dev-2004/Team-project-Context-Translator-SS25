/**
 * ExplanationItem - Interactive Web Component for Context Translator Explanations
 * 
 * This file implements a LitElement-based web component that displays individual explanation
 * items within the Context Translator application. The component provides a rich, interactive
 * card-based interface with expandable content, markdown rendering, and user actions.
 * 
 * Structure:
 * - ExplanationItem class: Main LitElement component extending web component functionality
 * - Static properties: Reactive property definitions for component state and callbacks
 * - CSS styles: Comprehensive Material Design 3 theming with hover states and animations
 * - Render method: Template structure defining the component's HTML output
 * - Event handlers: Methods for managing user interactions and component behavior
 * - Utility methods: Helper functions for markdown rendering and timestamp formatting
 * 
 * Purpose:
 * - Display explanation data in an accessible, interactive card format
 * - Provide expandable content view with smooth animations
 * - Enable user actions like pinning, deleting, and copying explanations
 * - Render markdown content with proper formatting and fallback handling
 * - Integrate with Material Design 3 theming system for consistent UI
 * 
 * Key Features:
 * - Expandable/collapsible content with smooth transitions
 * - Markdown rendering with fallback to basic HTML formatting
 * - Pin/unpin functionality with visual indicators
 * - Soft delete capability through callback system
 * - Copy-to-clipboard functionality
 * - Responsive design with hover states and accessibility features
 * - Material Design 3 theming integration
 * - Timestamp formatting with localization support
 * 
 * Disclaimer: Some portions of this code were generated using AI assistance
 * to ensure best practices and comprehensive functionality.
 */

import { LitElement, html, css } from 'lit';
import { marked } from 'marked';

/**
 * ExplanationItem Web Component
 * LitElement-based component for displaying individual explanation items
 * with interactive features, markdown rendering, and Material Design styling
 */
export class ExplanationItem extends LitElement {
  /**
   * Static Property Definitions
   * Defines reactive properties that trigger re-renders when changed
   * Includes explanation data, expanded state, and callback functions
   */
  static properties = {
    explanation: { type: Object },
    expanded: { type: Boolean },
    onPin: { type: Function },
    onDelete: { type: Function },
    onCopy: { type: Function }
  };

  /**
   * Component Styles
   * Comprehensive CSS styling using Material Design 3 design tokens
   * Includes responsive design, animations, and accessibility features
   */
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
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .pinned-indicator {
      color: var(--md-sys-color-secondary);
      font-size: 16px;
    }

    .explanation-actions {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .action-button {
      background: none;
      border: none;
      border-radius: 50%;
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: var(--md-sys-color-on-surface-variant);
      transition: all 0.2s ease;
      font-size: 16px;
    }

    .action-button:hover {
      background: var(--md-sys-color-surface-container);
      color: var(--md-sys-color-on-surface);
    }

    .pin-button.pinned {
      color: var(--md-sys-color-secondary);
      background: var(--md-sys-color-secondary-container);
    }

    .delete-button:hover {
      background: var(--md-sys-color-error-container);
      color: var(--md-sys-color-on-error-container);
    }

    .expand-icon {
      transition: transform 0.3s ease;
      cursor: pointer;
      padding: 8px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      color: var(--md-sys-color-on-surface-variant);
    }

    .expand-icon:hover {
      background: var(--md-sys-color-surface-container);
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

    .copy-button {
      background: var(--md-sys-color-primary-container);
      color: var(--md-sys-color-on-primary-container);
      border: none;
      border-radius: 20px;
      padding: 8px 16px;
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s ease;
    }

    .copy-button:hover {
      background: var(--md-sys-color-primary);
      color: var(--md-sys-color-on-primary);
    }

    .markdown-content strong {
      font-weight: 600;
    }

    .markdown-content em {
      font-style: italic;
    }

    .markdown-content code {
      background: var(--md-sys-color-surface-container-high);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Courier New', monospace;
      font-size: 0.9em;
    }

    .markdown-content ul, .markdown-content ol {
      margin: 8px 0;
      padding-left: 20px;
    }

    .markdown-content li {
      margin: 4px 0;
    }

    .markdown-content h1, .markdown-content h2, .markdown-content h3 {
      margin: 16px 0 8px 0;
      font-weight: 600;
    }

    .markdown-content h1 { font-size: 1.5em; }
    .markdown-content h2 { font-size: 1.3em; }
    .markdown-content h3 { font-size: 1.1em; }
  `;

  /**
   * Component Constructor
   * Initializes component state with default values
   * Sets expanded state to false and empty explanation object
   */
  constructor() {
    super();
    this.expanded = false;
    this.explanation = {};
  }

  /**
   * Component Render Method
   * Returns the HTML template for the component based on current state
   * Handles deleted explanations by returning empty template
   */
  render() {
    if (this.explanation.isDeleted) {
      return html``;
    }

    return html`
      <div class="explanation-card ${this.explanation.isPinned ? 'pinned' : ''}">
        <div class="explanation-header" @click=${this._toggleExpanded}>
          <div class="explanation-title">
            ${this.explanation.isPinned ? html`<span class="pinned-indicator">📌 </span>` : ''}
            ${this.explanation.title}
          </div>
          <div class="explanation-actions" @click=${this._stopPropagation}>
            <button class="action-button pin-button ${this.explanation.isPinned ? 'pinned' : ''}" 
                    @click=${this._handlePin} 
                    title="${this.explanation.isPinned ? 'Unpin' : 'Pin'} explanation">
              ${this.explanation.isPinned ? '📌' : '📌'}
            </button>
            <button class="action-button delete-button" @click=${this._handleDelete} title="Delete explanation">
              ✕
            </button>
          </div>
          <div class="expand-icon ${this.expanded ? 'expanded' : ''}" title="Toggle explanation">
            ▼
          </div>
        </div>
        
        <div class="explanation-content ${this.expanded ? 'expanded' : ''}">
          <div class="explanation-body">
            <div class="explanation-text markdown-content">
              ${this._renderMarkdown(this.explanation.content)}
            </div>
            <div class="explanation-footer">
              <span class="explanation-timestamp">
                ${this._formatTimestamp(this.explanation.timestamp)}
              </span>
              <button class="copy-button" @click=${this._handleCopy} title="Copy explanation">
                📋 Copy
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Toggle Expanded State
   * Toggles the expanded/collapsed state of the explanation content
   * Triggers re-render with updated expansion state
   */
  _toggleExpanded() {
    this.expanded = !this.expanded;
  }

  /**
   * Stop Event Propagation
   * Prevents event bubbling to parent elements
   * Used for action buttons to prevent header click handling
   */
  _stopPropagation(e) {
    e.stopPropagation();
  }

  /**
   * Handle Pin Action
   * Processes pin/unpin button clicks and invokes callback
   * Prevents event propagation to avoid triggering expansion
   */
  _handlePin(e) {
    e.stopPropagation();
    if (this.onPin) {
      this.onPin(this.explanation.id);
    }
  }

  /**
   * Handle Delete Action
   * Processes delete button clicks and invokes callback
   * Prevents event propagation to avoid triggering expansion
   */
  _handleDelete(e) {
    e.stopPropagation();
    if (this.onDelete) {
      this.onDelete(this.explanation.id);
    }
  }

  /**
   * Handle Copy Action
   * Processes copy button clicks and invokes callback with explanation data
   * Used for copying explanation content to clipboard
   */
  _handleCopy() {
    if (this.onCopy) {
      this.onCopy(this.explanation);
    }
  }

  /**
   * Render Markdown Content
   * Converts markdown text to HTML using the marked library
   * Includes fallback handling for parsing errors with basic text formatting
   */
  _renderMarkdown(content) {
    if (!content) return html``;
    
    try {
      marked.setOptions({
        breaks: true,
        gfm: true,
        sanitize: false,
        smartLists: true,
        smartypants: false
      });
      
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

  /**
   * Format Timestamp Display
   * Converts timestamp to localized German date/time format
   * Returns formatted string or empty string if no timestamp provided
   */
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

/**
 * Custom Element Registration
 * Registers the ExplanationItem component as a custom HTML element
 * Makes the component available for use as <explanation-item> tag
 */
customElements.define('explanation-item', ExplanationItem);