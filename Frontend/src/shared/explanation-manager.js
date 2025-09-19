// flattened copy from shared/src/explanation-manager.js
export class ExplanationManager {
  constructor() {
    this.explanations = [];
    this.listeners = [];
    this.storageKey = 'context-translator-explanations';
    this.saveThrottleTimeout = null;
    this.loadFromStorage();
  }
  static getInstance() { if (!ExplanationManager.instance) ExplanationManager.instance = new ExplanationManager(); return ExplanationManager.instance; }
  addListener(cb) { this.listeners.push(cb); }
  removeListener(cb) { this.listeners = this.listeners.filter(l => l !== cb); }
  notifyListeners() { this.listeners.forEach(cb => cb(this.explanations)); }
  addExplanation(title, content, timestamp = Date.now(), confidence = null) {
    // Clamp and normalize confidence to [0,1] if provided
    const normConfidence = (typeof confidence === 'number' && isFinite(confidence))
      ? Math.max(0, Math.min(1, confidence))
      : null;
    const explanation = { id: this._generateId(), title, content, timestamp, confidence: normConfidence, isPinned: false, isDeleted: false, createdAt: Date.now() };
    this.explanations.unshift(explanation); this._sortExplanations(); this._saveToStorageThrottled(); this.notifyListeners(); return explanation;
  }
  updateExplanation(id, updates) {
    const i = this.explanations.findIndex(e => e.id === id);
    if (i !== -1) {
      // Normalize confidence if present in updates
      let normUpdates = { ...updates };
      if ('confidence' in normUpdates) {
        const c = normUpdates.confidence;
        normUpdates.confidence = (typeof c === 'number' && isFinite(c))
          ? Math.max(0, Math.min(1, c))
          : null;
      }
      this.explanations[i] = { ...this.explanations[i], ...normUpdates };
      this._sortExplanations();
      this._saveToStorageThrottled();
      this.notifyListeners();
      return this.explanations[i];
    }
    return null;
  }
  deleteExplanation(id) { const i = this.explanations.findIndex(e => e.id === id); if (i !== -1) { this.explanations[i].isDeleted = true; this._saveToStorageThrottled(); this.notifyListeners(); } }
  pinExplanation(id) { const e = this.explanations.find(e => e.id === id); if (e) { e.isPinned = !e.isPinned; this._sortExplanations(); this._saveToStorageThrottled(); this.notifyListeners(); } }
  _sortExplanations() { this.explanations.sort((a,b)=> (a.isPinned===b.isPinned ? b.createdAt-a.createdAt : a.isPinned?-1:1)); }
  getVisibleExplanations() { return this.explanations.filter(e => !e.isDeleted); }
  clearAll() { this.explanations = []; this.saveToStorage(); this.notifyListeners(); }
  _saveToStorageThrottled() {
    // Throttle storage saves to prevent excessive I/O during rapid explanation additions
    if (this.saveThrottleTimeout) {
      clearTimeout(this.saveThrottleTimeout);
    }
    this.saveThrottleTimeout = setTimeout(() => {
      this.saveToStorage();
      this.saveThrottleTimeout = null;
    }, 500); // Save after 500ms of inactivity
  }
  saveToStorage() { try { sessionStorage.setItem(this.storageKey, JSON.stringify(this.explanations)); } catch (e) { console.error('Failed to save explanations to storage:', e); } }
  loadFromStorage() { try { const stored = sessionStorage.getItem(this.storageKey); if (stored) { this.explanations = JSON.parse(stored); this._sortExplanations(); } } catch (e) { console.error('Failed to load explanations from storage:', e); this.explanations = []; } }
  _generateId() { return `exp_${Date.now()}_${Math.random().toString(36).substr(2,9)}`; }
}
export const explanationManager = ExplanationManager.getInstance();
