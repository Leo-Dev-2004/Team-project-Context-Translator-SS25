// frontend/src/modules/preload.js (CommonJS)
// Hinweis: Preload läuft im isolierten Kontext. Wir exponieren gezielt nur eine kleine, sichere API.
const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),

  // Settings management
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  loadSettings: () => ipcRenderer.invoke('load-settings'),

  // File dialogs
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),

  // Platform detection
  platform: process.platform,
  isElectron: true,

  // Node.js info (safe to expose)
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron
  },

  // Mache den Handler für die User Session ID verfügbar
  getUserSessionId: () => ipcRenderer.invoke('get-user-session-id'),

  // Window controls
  windowControls: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    unmaximize: () => ipcRenderer.invoke('window:unmaximize'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
    close: () => ipcRenderer.invoke('window:close'),
    onMaximized: (cb) => ipcRenderer.on('window:maximized', cb),
    onUnmaximized: (cb) => ipcRenderer.on('window:unmaximized', cb)
  }
})

// Log when preload script is loaded
console.log('Preload script loaded (using CommonJS syntax)');
// Hinweis: Die frühere Verwendung von exposeInIsolatedWorld war fehlerhaft (falsche Argumente)
// und führte zu einem Preload-Crash. Falls zukünftig zusätzliche Kanäle nötig sind,
// diese bitte ebenfalls über exposeInMainWorld bereitstellen.