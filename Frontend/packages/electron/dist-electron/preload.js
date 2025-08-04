// src/preload.js
var import_electron = require("electron");
import_electron.contextBridge.exposeInMainWorld("electronAPI", {
  // App info
  getAppVersion: () => import_electron.ipcRenderer.invoke("get-app-version"),
  getPlatform: () => import_electron.ipcRenderer.invoke("get-platform"),
  // Settings management
  saveSettings: (settings) => import_electron.ipcRenderer.invoke("save-settings", settings),
  loadSettings: () => import_electron.ipcRenderer.invoke("load-settings"),
  // File dialogs
  showSaveDialog: (options) => import_electron.ipcRenderer.invoke("show-save-dialog", options),
  showOpenDialog: (options) => import_electron.ipcRenderer.invoke("show-open-dialog", options),
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
console.log("Preload script loaded");
