/**
 * Shared Styles Module
 * 
 * This file serves as the CSS-in-JS bridge for the shared package in the Team Project Context Translator.
 * It imports external CSS styles and converts them into Lit framework-compatible CSSResult objects
 * that can be used across different web components in the application.
 * 
 * The module utilizes Vite's CSS import feature with the '?inline' query parameter to import
 * CSS as a string, then transforms it using Lit's CSS utilities for safe consumption by
 * Lit web components.
 * 
 * Content:
 * - Import statements for Lit CSS utilities (css, unsafeCSS)
 * - Import of external CSS file as inline string
 * - Export of processed CSS as Lit CSSResult
 * 
 * Structure:
 * - External dependencies: Lit framework CSS utilities
 * - CSS import: External stylesheet imported as string via Vite
 * - Style processing: Conversion from CSS string to Lit CSSResult
 * 
 * Purpose:
 * - Bridge external CSS files with Lit web components
 * - Provide shared styling that can be imported by multiple components
 * - Enable consistent theming across the application
 * - Maintain separation between CSS definitions and JavaScript logic
 * 
 * Usage:
 * Components can import and use sharedStyles in their static styles property
 * to apply consistent styling across the application.
 * 
 * DISCLAIMER: Some portions of this code may have been generated or assisted by AI tools.
 */

// Import Lit CSS utilities for creating and processing CSS in web components
// css: Creates a CSSResult from a template literal
// unsafeCSS: Wraps a string as CSS without validation (used for external CSS)
import { css, unsafeCSS } from 'lit'

// Import external CSS file as an inline string using Vite's ?inline query parameter
// This allows the CSS content to be imported as a JavaScript string rather than
// being processed as a separate stylesheet file
import styles from './index.css?inline'

// Convert imported CSS string into a Lit CSSResult object
// This processed CSS can then be used in Lit components' static styles property
// unsafeCSS() wraps the external CSS string, and css`` creates the final CSSResult
export const sharedStyles = css`${unsafeCSS(styles)}`