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
const isFrameless = process.platform === 'win32' && !isDev;

// NEU: Lese die user_session_id aus den Kommandozeilen-Argumenten
const userSessionIdArg = process.argv.find(arg => arg.startsWith('--user-session-id='));
const userSessionId = userSessionIdArg ? userSessionIdArg.split('=')[1] : null;
if (userSessionId) {
  console.log(`Main: User Session ID found: ${userSessionId}`);
}


const settingsPath = join(os.homedir(), '.context-translator-settings.json');

function createWindow() {
  console.log('Main: ⚙️ Creating main window...');
  mainWindow = new BrowserWindow({
    // Vertikale, seitenleistenartige Standardgröße
    width: 420,
    height: 820,
    minWidth: 320,
    minHeight: 500,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: join(__dirname, '..', 'dist-electron', 'preload.js'),
      // Security hardening
      webSecurity: true,
      allowRunningInsecureContent: false,
      spellcheck: true
      },
    // Frameless nur auf Windows in Produktion, damit eigene Titlebar verwendet werden kann
    frame: isFrameless ? false : true,
    titleBarStyle: isFrameless ? 'hidden' : 'default',
    autoHideMenuBar: true,
    show: false,
    icon: join(__dirname, '../assets/icon.png')
  });
  console.log('Main: ✅ Main window created.');

  mainWindow.webContents.session.setSpellCheckerLanguages(['en-US', 'en-GB', 'de-DE']);
  console.log('Main: 🗣️ SpellChecker: Languages set to German and English.');

  // Sicherstellen, dass die Menüleiste ausgeblendet ist (Windows Alt-Taste)
  try { mainWindow.setMenuBarVisibility(false); } catch {}

  // Weiterleitung der Renderer-Konsolenlogs an den Main-Prozess-Log
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    // Filter out harmless DevTools protocol warnings
    if (message.includes('Autofill.setAddresses') || message.includes("'Autofill.setAddresses' wasn't found")) {
      return; // Suppress this known Electron/DevTools incompatibility warning
    }
    
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

  // Strict, environment-aware Content Security Policy
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const devCsp = [
      "default-src 'self' data: blob:",
      // Vite dev server: erlaub Inline für Styles, aber kein 'unsafe-eval' (vermeidet Warnung)
      "script-src 'self' http://localhost:5174",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: blob:",
      // Allow ws/http to vite and backend in dev
      "connect-src 'self' ws://localhost:5174 http://localhost:5174 ws://localhost:8000 http://localhost:8000",
      // Extra hardening
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'none'"
    ].join('; ');

    const prodCsp = [
      "default-src 'self' data: blob:",
      // No inline/eval scripts in production
      "script-src 'self'",
      // Allow Google Fonts CSS; keep inline styles if components rely on them
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: blob:",
      // Backend local API/WS endpoints
      "connect-src 'self' ws://localhost:8000 http://localhost:8000",
      // Extra hardening
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'none'"
    ].join('; ');

    const csp = isDev ? devCsp : prodCsp;
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [csp]
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

  // Fensterstatus an Renderer melden (für Maximize-Button-Zustand)
  mainWindow.on('maximize', () => {
    if (mainWindow) mainWindow.webContents.send('window:maximized');
  });
  mainWindow.on('unmaximize', () => {
    if (mainWindow) mainWindow.webContents.send('window:unmaximized');
  });
}

// App event handlers
app.whenReady().then(() => {
    // Erstelle den IPC-Handler, bevor das Fenster erstellt wird
  ipcMain.handle('get-user-session-id', () => {
    return userSessionId;
  });

  console.log('Main: ✅ App is ready. Calling createWindow...');
  console.log(`Main: 📁 Settings will be saved to: ${settingsPath}`);
  createWindow();
  // In Dev das Menü behalten, in Prod entfernen für aufgeräumtes UI
  if (isDev) {
    createMenu();
  } else {
    Menu.setApplicationMenu(null);
  }

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
  version: process.getSystemVersion(),
  frameless: isFrameless
  };
});

ipcMain.handle('save-settings', async (event, settings) => {
  const timestamp = new Date().toISOString();
  console.log(`Main: 💾 [${timestamp}] Received save-settings IPC request`);
  console.log('Main:    Settings to save:', JSON.stringify(settings));
  console.log('Main:    Target file:', settingsPath);
  
  try {
    const settingsData = {
      ...settings,
      lastUpdated: new Date().toISOString()
    };
    
    console.log('Main: 📝 Writing settings to file...');
    await fs.writeFile(settingsPath, JSON.stringify(settingsData, null, 2));
    console.log('Main: ✅ Settings successfully saved to:', settingsPath);
    
    // Verify the file was written by reading it back
    try {
      const savedContent = await fs.readFile(settingsPath, 'utf8');
      const savedData = JSON.parse(savedContent);
      console.log('Main: ✓ Verified settings file written with keys:', Object.keys(savedData));
    } catch (verifyError) {
      console.warn('Main: ⚠️ Could not verify saved file:', verifyError.message);
    }
    
    return { success: true };
  } catch (error) {
    console.error('Main: ❌ Failed to save settings:', error);
    console.error('Main:    Error details:', error.message);
    console.error('Main:    Target file was:', settingsPath);
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

// Fenstersteuerungs-IPC
ipcMain.handle('window:minimize', () => {
  if (mainWindow) mainWindow.minimize();
});
ipcMain.handle('window:maximize', () => {
  if (mainWindow && !mainWindow.isMaximized()) mainWindow.maximize();
});
ipcMain.handle('window:unmaximize', () => {
  if (mainWindow && mainWindow.isMaximized()) mainWindow.unmaximize();
});
ipcMain.handle('window:isMaximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});
ipcMain.handle('window:close', () => {
  if (mainWindow) mainWindow.close();
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