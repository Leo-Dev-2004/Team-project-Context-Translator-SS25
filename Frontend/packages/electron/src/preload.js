// frontend/src/modules/preload.js (UMGESTELLTE VERSION MIT require())

// Verwenden Sie require() anstelle von import für Electron-Module
// Dies ist notwendig, wenn Ihr Electron-Hauptprozess (oder der Kontext, in dem preload.js läuft)
// nicht explizit als ES-Modul konfiguriert ist oder wenn ein Bundler
// die import-Statements nicht korrekt verarbeitet.
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
  }
});

// Log when preload script is loaded
console.log('Preload script loaded (using CommonJS syntax)');