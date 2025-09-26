// Constants for explanation-related strings to avoid tight coupling
// between the explanation manager and UI layer

export const EXPLANATION_CONSTANTS = {
  // Loading/Processing states
  GENERATING_EMOJI: '🔄',
  GENERATING_PREFIX: 'Generating explanation for',
  GENERATING_SUFFIX: '...',
  GENERATING_DISPLAY_TEXT: 'Generating explanation...',
  
  // Patterns for content detection
  LOADING_PATTERN: '🔄 Generating explanation',
  
  // UI replacement text
  ANALYZING_PREFIX: 'Analyzing term:',
};

/**
 * Creates a loading message for a specific term
 * @param {string} term - The term being explained
 * @param {string} context - The context for the term (optional)
 * @returns {string} - Formatted loading message
 */
export function createLoadingMessage(term, context = '') {
  // Validate term parameter
  if (!term || typeof term !== 'string' || term.trim() === '') {
    console.warn('createLoadingMessage: Invalid term provided:', term);
    term = 'Unknown Term';
  }
  
  const baseMessage = `${EXPLANATION_CONSTANTS.GENERATING_EMOJI} ${EXPLANATION_CONSTANTS.GENERATING_PREFIX} "${term.trim()}"${EXPLANATION_CONSTANTS.GENERATING_SUFFIX}`;
  return context ? `${baseMessage}\n\n**Context:** ${context}` : baseMessage;
}

/**
 * Checks if content is in a loading state
 * @param {string} content - Content to check
 * @returns {boolean} - True if content is in loading state
 */
export function isLoadingContent(content) {
  return Boolean(content && content.includes(EXPLANATION_CONSTANTS.LOADING_PATTERN));
}

/**
 * Formats content for display during loading state
 * @param {string} content - Loading content
 * @returns {string} - Formatted content for display
 */
export function formatLoadingDisplay(content) {
  return content
    .replace(`${EXPLANATION_CONSTANTS.GENERATING_EMOJI} ${EXPLANATION_CONSTANTS.GENERATING_PREFIX}`, EXPLANATION_CONSTANTS.ANALYZING_PREFIX)
    .replace(EXPLANATION_CONSTANTS.GENERATING_SUFFIX, '');
}