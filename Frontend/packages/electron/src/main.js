// src/main.js
import { app, BrowserWindow, ipcMain, Menu, session, dialog } from 'electron'; // << Added session and dialog here
import { fileURLToPath } from 'url';
import { dirname, join } from 'path'; // `path` is already imported from Node.js
import os from 'os';
import fs from 'fs/promises'; // << Import fs with promises for async operations

// ESM equivalent of __filename and __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const isDev = process.env.NODE_ENV === 'development';
let mainWindow;

// Settings storage path
const settingsPath = join(os.homedir(), '.context-translator-settings.json');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      // Path to the bundled preload script (esbuild outputs CommonJS)
      preload: join(__dirname, '..', 'dist-electron', 'preload.js'),
      webSecurity: isDev ? false : true, // Disable webSecurity in dev for easier local testing, enable in prod
    },
    titleBarStyle: 'default',
    show: false,
    icon: join(__dirname, '../assets/icon.png') // Add icon if available
  });

  // CSP headers for security within session.defaultSession.webRequest.onHeadersReceived
  // This block must be *inside* createWindow and *after* mainWindow is created,
  // but *before* loading the URL, as it affects headers of the loaded content.
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          `default-src 'self' data: blob:;` +
          `script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:5174;` + // 'unsafe-eval' often needed for Vite HMR
          `font-src 'self' data: https://fonts.gstatic.com;` + // <<< Added fonts.gstatic.com
          `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;` + // <<< Added fonts.googleapis.com
          `img-src 'self' data:;` +
          `connect-src 'self' ws://localhost:5174 http://localhost:5174;` // ws:// needed for Vite HMR
        ]
      }
    });
  });

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5174');
    mainWindow.webContents.openDevTools();
  } else {
    // Correct path for production build
    mainWindow.loadFile(join(__dirname, '../renderer/dist/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    if (isDev) {
      // DevTools are already opened if isDev
      // mainWindow.webContents.openDevTools(); 
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createMenu() {
  const template = [
    {
      label: 'Context Translator',
      submenu: [
        {
          label: 'About Context Translator',
          click: () => {
            // Show about dialog
          }
        },
        { type: 'separator' },
        { role: 'quit' }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectall' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// App event handlers
app.whenReady().then(() => {
  createWindow();
  createMenu();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-platform', () => {
  return {
    platform: process.platform,
    arch: process.arch,
    version: process.getSystemVersion()
  };
});

ipcMain.handle('save-settings', async (event, settings) => {
  try {
    const settingsData = {
      ...settings,
      lastUpdated: new Date().toISOString()
    };
    
    await fs.writeFile(settingsPath, JSON.stringify(settingsData, null, 2));
    return { success: true };
  } catch (error) {
    console.error('Failed to save settings:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('load-settings', async () => {
  try {
    const data = await fs.readFile(settingsPath, 'utf8');
    return { success: true, settings: JSON.parse(data) };
  } catch (error) {
    if (error.code === 'ENOENT') {
      return { success: true, settings: null }; // No settings file yet
    }
    console.error('Failed to load settings:', error);
    return { success: false, error: error.message };
  }
});

// `dialog` is now imported at the top, no need for dynamic import here
ipcMain.handle('show-save-dialog', async (event, options) => {
  const result = await dialog.showSaveDialog(mainWindow, options);
  return result;
});

// `dialog` is now imported at the top
ipcMain.handle('show-open-dialog', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options);
  return result;
});