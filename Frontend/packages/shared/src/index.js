/**
 * Shared Package Index Module
 * 
 * This file serves as the main entry point for the shared package in the Team Project Context Translator.
 * It exports commonly used components, utilities, and managers that are shared across different parts
 * of the frontend application.
 * 
 * The file acts as a barrel export, consolidating imports from various modules within the shared package
 * to provide a clean and organized API for consuming applications. This includes UI components, styling
 * utilities, explanation-related functionality, and management classes.
 * 
 * Structure:
 * - UI components and utilities from ui.js
 * - Shared styling configurations from styles.js
 * - Explanation item component from explanation-item.js
 * - Explanation management functionality from explanation-manager.js
 * 
 * Purpose:
 * - Centralize exports for the shared package
 * - Provide a single import source for shared functionality
 * - Maintain clean separation of concerns across modules
 * - Enable easy consumption of shared resources by other packages
 * 
 * DISCLAIMER: Some portions of this code may have been generated or assisted by AI tools.
 */

// Export UI component and utilities - provides core user interface elements and helper functions
export { UI } from './ui.js'

// Export shared styling configurations - contains common CSS-in-JS styles and theming
export { sharedStyles } from './styles.js'

// Export ExplanationItem component - individual explanation display component for context translations
export { ExplanationItem } from './explanation-item.js'

// Export explanation management functionality - includes both the manager instance and class
// explanationManager: singleton instance for managing explanation state
// ExplanationManager: class definition for creating explanation managers
export { explanationManager, ExplanationManager } from './explanation-manager.js'