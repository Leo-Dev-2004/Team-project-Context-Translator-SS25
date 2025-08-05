// src/main.js
import { app, BrowserWindow, ipcMain, Menu, session, dialog } from 'electron';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import os from 'os';
import fs from 'fs/promises';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const isDev = process.env.NODE_ENV === 'development';
let mainWindow;

const settingsPath = join(os.homedir(), '.context-translator-settings.json');

function createWindow() {
  console.log('Main: ⚙️ Creating main window...');
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: join(__dirname, '..', 'dist-electron', 'preload.js'),
      webSecurity: isDev ? false : true,
    },
    titleBarStyle: 'default',
    show: false,
    icon: join(__dirname, '../assets/icon.png')
  });
  console.log('Main: ✅ Main window created.');

  // Weiterleitung der Renderer-Konsolenlogs an den Main-Prozess-Log
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    const logPrefix = `[Renderer]`;
    if (level === 0) {
      console.log(`${logPrefix} ${message}`);
    } else if (level === 1) {
      console.warn(`${logPrefix} ${message}`);
    } else if (level === 2) {
      console.error(`${logPrefix} ${message}`);
    }
  });

  // Hinzugefügtes Logging für den Lade-Prozess
  mainWindow.webContents.on('did-start-loading', () => {
    console.log('Main: 💡 WebContents started loading...');
  });
  mainWindow.webContents.on('did-stop-loading', () => {
    console.log('Main: ✅ WebContents stopped loading.');
  });
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('Main: ✅ WebContents finished loading successfully.');
  });
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    console.error(`Main: ❌ Failed to load URL: ${validatedURL}, ErrorCode: ${errorCode}, Description: ${errorDescription}`);
    mainWindow.loadURL(`data:text/html,<h1>Failed to load: ${errorDescription}</h1>`);
  });

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          `default-src 'self' data: blob:;` +
          `script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:5174;` +
          `font-src 'self' data: https://fonts.gstatic.com;` +
          `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;` +
          `img-src 'self' data:;` +
          `connect-src 'self' ws://localhost:5174 http://localhost:5174;`
        ]
      }
    });
  });

  if (isDev) {
    console.log('Main: 💡 Running in development mode. Loading Vite URL...');
    mainWindow.loadURL('http://localhost:5174');
    mainWindow.webContents.openDevTools();
  } else {
    console.log('Main: 💡 Running in production mode. Loading file...');
    mainWindow.loadFile(join(__dirname, '../renderer/dist/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    console.log('Main: ✅ Window is ready to show. Showing window.');
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    console.log('Main: ⚙️ Main window closed. Setting mainWindow to null.');
    mainWindow = null;
  });
}

// App event handlers
app.whenReady().then(() => {
  console.log('Main: ✅ App is ready. Calling createWindow...');
  createWindow();
  createMenu();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      console.log('Main: ⚙️ App activated, no windows open. Creating a new one.');
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  console.log('Main: ⚙️ All windows closed. Quitting app if not on macOS.');
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
      return { success: true, settings: null };
    }
    console.error('Failed to load settings:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('show-save-dialog', async (event, options) => {
  const result = await dialog.showSaveDialog(mainWindow, options);
  return result;
});

ipcMain.handle('show-open-dialog', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options);
  return result;
});


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