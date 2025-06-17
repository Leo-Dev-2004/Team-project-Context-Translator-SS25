export class ExplanationManager {
  constructor() {
    this.explanations = [];
    this.listeners = [];
    this.storageKey = 'context-translator-explanations';
    this.loadFromStorage();
  }

  // Singleton Pattern
  static getInstance() {
    if (!ExplanationManager.instance) {
      ExplanationManager.instance = new ExplanationManager();
    }
    return ExplanationManager.instance;
  }

  // Event Listener Management
  addListener(callback) {
    this.listeners.push(callback);
  }

  removeListener(callback) {
    this.listeners = this.listeners.filter(listener => listener !== callback);
  }

  notifyListeners() {
    this.listeners.forEach(callback => callback(this.explanations));
  }
  // CRUD Operations
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

  deleteExplanation(id) {
    const index = this.explanations.findIndex(exp => exp.id === id);
    if (index !== -1) {
      this.explanations[index].isDeleted = true;
      this.saveToStorage();
      this.notifyListeners();
    }
  }
  pinExplanation(id) {
    const explanation = this.explanations.find(exp => exp.id === id);
    if (explanation) {
      explanation.isPinned = !explanation.isPinned;
      this._sortExplanations(); // Re-sort immediately after pinning
      this.saveToStorage();
      this.notifyListeners();
    }
  }

  // Helper method to sort explanations (pinned always on top)
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

  getVisibleExplanations() {
    return this.explanations.filter(exp => !exp.isDeleted);
  }

  clearAll() {
    this.explanations = [];
    this.saveToStorage();
    this.notifyListeners();
  }

  // Storage Management
  saveToStorage() {
    try {
      sessionStorage.setItem(this.storageKey, JSON.stringify(this.explanations));
    } catch (error) {
      console.error('Failed to save explanations to storage:', error);
    }
  }
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

  // Helper Methods
  _generateId() {
    return `exp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Export singleton instance
export const explanationManager = ExplanationManager.getInstance();