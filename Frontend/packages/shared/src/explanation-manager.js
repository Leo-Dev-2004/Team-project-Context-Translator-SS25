/**
 * ExplanationManager - Centralized Management System for Context Translator Explanations
 * 
 * This file implements a singleton pattern-based manager for handling explanation data
 * within the Context Translator application. It provides comprehensive CRUD operations,
 * event-driven architecture for UI updates, and persistent storage capabilities.
 * 
 * Structure:
 * - ExplanationManager class: Main singleton class handling all explanation operations
 * - Event listener system: Observer pattern implementation for reactive UI updates
 * - Storage layer: SessionStorage-based persistence with error handling
 * - Sorting system: Intelligent sorting with pinned items prioritization
 * 
 * Purpose:
 * - Centralize explanation data management across the application
 * - Provide consistent CRUD operations with proper state management
 * - Enable reactive UI updates through event listeners
 * - Maintain data persistence across browser sessions
 * - Support advanced features like pinning and soft deletion
 * 
 * Key Features:
 * - Singleton pattern ensures single source of truth
 * - Observer pattern for decoupled UI updates
 * - Intelligent sorting (pinned items first, then by creation date)
 * - Soft deletion system for data recovery
 * - Robust error handling for storage operations
 * 
 * Disclaimer: Some portions of this code were generated using AI assistance
 * to ensure best practices and comprehensive functionality.
 */

/**
 * ExplanationManager Class
 * Singleton class that manages all explanation-related operations including
 * creation, updating, deletion, storage, and event handling for the Context Translator
 */
export class ExplanationManager {
  /**
   * Constructor - Initializes the ExplanationManager instance
   * Sets up initial state with empty arrays for explanations and listeners,
   * defines storage key, and loads existing data from storage
   */
  constructor() {
    this.explanations = [];
    this.listeners = [];
    this.storageKey = 'context-translator-explanations';
    this.loadFromStorage();
  }

  /**
   * Singleton Pattern Implementation
   * Ensures only one instance of ExplanationManager exists throughout the application
   * Returns the existing instance or creates a new one if none exists
   */
  static getInstance() {
    if (!ExplanationManager.instance) {
      ExplanationManager.instance = new ExplanationManager();
    }
    return ExplanationManager.instance;
  }

  /**
   * Event Listener Registration
   * Adds a callback function to the listeners array for reactive updates
   * Callback will be invoked whenever explanations data changes
   */
  addListener(callback) {
    this.listeners.push(callback);
  }

  /**
   * Event Listener Removal
   * Removes a specific callback function from the listeners array
   * Used for cleanup when components are unmounted or no longer need updates
   */
  removeListener(callback) {
    this.listeners = this.listeners.filter(listener => listener !== callback);
  }

  /**
   * Event Notification System
   * Invokes all registered callback functions with current explanations data
   * Enables reactive UI updates across all subscribed components
   */
  notifyListeners() {
    this.listeners.forEach(callback => callback(this.explanations));
  }

  /**
   * Create New Explanation
   * Adds a new explanation to the collection with generated ID and metadata
   * Automatically sorts the collection, saves to storage, and notifies listeners
   * Returns the created explanation object
   */
  addExplanation(title, content, timestamp = Date.now()) {
    const explanation = {
      id: this._generateId(),
      title,
      content,
      timestamp,
      isPinned: false,
      isDeleted: false,
      createdAt: Date.now()
    };

    this.explanations.unshift(explanation); // Neue Erklärungen oben
    this._sortExplanations(); // Ensure proper sorting
    this.saveToStorage();
    this.notifyListeners();
    return explanation;
  }

  /**
   * Update Existing Explanation
   * Finds and updates an explanation by ID with provided updates object
   * Maintains proper sorting, saves changes, and notifies listeners
   * Returns the updated explanation or null if not found
   */
  updateExplanation(id, updates) {
    const index = this.explanations.findIndex(exp => exp.id === id);
    if (index !== -1) {
      this.explanations[index] = { ...this.explanations[index], ...updates };
      this._sortExplanations(); // Ensure proper sorting after update
      this.saveToStorage();
      this.notifyListeners();
      return this.explanations[index];
    }
    return null;
  }

  /**
   * Soft Delete Explanation
   * Marks an explanation as deleted without removing it from the array
   * Enables potential data recovery and maintains referential integrity
   * Updates storage and notifies listeners of the change
   */
  deleteExplanation(id) {
    const index = this.explanations.findIndex(exp => exp.id === id);
    if (index !== -1) {
      this.explanations[index].isDeleted = true;
      this.saveToStorage();
      this.notifyListeners();
    }
  }

  /**
   * Toggle Explanation Pin Status
   * Toggles the isPinned status of an explanation and triggers re-sorting
   * Pinned explanations appear at the top of the list
   * Updates storage and notifies listeners after the change
   */
  pinExplanation(id) {
    const explanation = this.explanations.find(exp => exp.id === id);
    if (explanation) {
      explanation.isPinned = !explanation.isPinned;
      this._sortExplanations(); // Re-sort immediately after pinning
      this.saveToStorage();
      this.notifyListeners();
    }
  }

  /**
   * Internal Sorting Algorithm
   * Sorts explanations with pinned items first, then by creation date (newest first)
   * Maintains consistent ordering with pinned items always at the top
   * Called automatically after operations that affect order
   */
  _sortExplanations() {
    this.explanations.sort((a, b) => {
      // Pinned items always come first
      if (a.isPinned && !b.isPinned) return -1;
      if (!a.isPinned && b.isPinned) return 1;
      
      // Among pinned items, sort by creation time (newest first)
      if (a.isPinned && b.isPinned) {
        return b.createdAt - a.createdAt;
      }
      
      // Among unpinned items, sort by creation time (newest first)
      return b.createdAt - a.createdAt;
    });
  }

  /**
   * Get Visible Explanations
   * Filters out soft-deleted explanations and returns only visible ones
   * Used by UI components to display current active explanations
   * Does not modify the original explanations array
   */
  getVisibleExplanations() {
    return this.explanations.filter(exp => !exp.isDeleted);
  }

  /**
   * Clear All Explanations
   * Removes all explanations from the collection and storage
   * Provides a complete reset functionality for the explanation system
   * Updates storage and notifies all listeners of the change
   */
  clearAll() {
    this.explanations = [];
    this.saveToStorage();
    this.notifyListeners();
  }

  /**
   * Persist Data to Storage
   * Saves the current explanations array to sessionStorage as JSON
   * Includes error handling for storage quota exceeded or other storage issues
   * Ensures data persistence across browser sessions
   */
  saveToStorage() {
    try {
      sessionStorage.setItem(this.storageKey, JSON.stringify(this.explanations));
    } catch (error) {
      console.error('Failed to save explanations to storage:', error);
    }
  }

  /**
   * Load Data from Storage
   * Retrieves and parses explanations data from sessionStorage
   * Includes error handling and automatic sorting after loading
   * Initializes with empty array if no data exists or parsing fails
   */
  loadFromStorage() {
    try {
      const stored = sessionStorage.getItem(this.storageKey);
      if (stored) {
        this.explanations = JSON.parse(stored);
        this._sortExplanations(); // Ensure proper sorting when loading
      }
    } catch (error) {
      console.error('Failed to load explanations from storage:', error);
      this.explanations = [];
    }
  }

  /**
   * Generate Unique Identifier
   * Creates a unique ID string combining timestamp and random characters
   * Ensures each explanation has a unique identifier for tracking and operations
   * Returns a string in format: "exp_timestamp_randomstring"
   */
  _generateId() {
    return `exp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

/**
 * Singleton Instance Export
 * Pre-instantiated singleton instance ready for import and use
 * Provides immediate access to the ExplanationManager without manual instantiation
 */
export const explanationManager = ExplanationManager.getInstance();