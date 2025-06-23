/**
 * ExplanationItem - Interactive Web Component for Context Translator Explanatio    return html`
      <div class="explanation-item-host">
        <div class="explanation-card ${this.explanation.isPinned ? 'pinned' : ''}">`
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

import { LitElement, html } from 'lit';
import { marked } from 'marked';
import { sharedStyles } from './styles.js';

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
   * Uses shared styles from centralized CSS
   */
  static styles = [sharedStyles]

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
            </div>          </div>
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