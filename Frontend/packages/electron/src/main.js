import { app, BrowserWindow, ipcMain, Menu } from 'electron'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import fs from 'fs/promises'
import os from 'os'
import { spawn } from 'child_process'
import path from 'path'

let pythonProcess = null

console.log('--- main.js started executing ---'); // <<< FÜGEN SIE DIESE ZEILE HIER HINZU!

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const isDev = process.env.NODE_ENV === 'development'
let mainWindow

// Settings storage path
const settingsPath = join(os.homedir(), '.context-translator-settings.json')

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: join(__dirname, 'preload.js'),
      webSecurity: true
    },
    titleBarStyle: 'default',
    show: false,
    icon: join(__dirname, '../assets/icon.png') // Add icon if available
  })

function startPythonSTTProcess() {
  if (pythonProcess) {
    console.log('Python STT process already running.')
    return
  }

  const pythonScriptPath = path.join(__dirname, '..', '..', 'Backend', 'STT', 'transcribe.py')

  pythonProcess = spawn('python', [pythonScriptPath], {
    stdio: ['pipe', 'pipe', 'pipe'],
    cwd: path.dirname(pythonScriptPath),
    env: process.env
  })

  pythonProcess.stdout.setEncoding('utf8')
  pythonProcess.stdout.on('data', (data) => {
    data.trim().split('\n').forEach(line => {
      try {
        const msg = JSON.parse(line)
        console.log('Received from Python:', msg)
        if (msg.status === 'success') {
          mainWindow?.webContents.send('python-response', msg)
        } else if (msg.status === 'error') {
          console.error('Fehlermeldung von Python:', msg.message)
          mainWindow?.webContents.send('python-error',msg)
        } else {
          mainWindow?.webContents.send('python-event', msg)
        }
      } catch (e) {
        console.error('Error parsing Python stdout line:', line)
      }
    })
  })
  pythonProcess.stderr.setEncoding('utf8')
  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python STDERR: ${data}`)
  })

  pythonProcess.on('close', (code) => {
    console.log(`Python process exit with code ${code}`)
    pythonProcess = null
  })
}
  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5174')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(join(__dirname, '../dist/index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    
    if (isDev) {
      mainWindow.webContents.openDevTools()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
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
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}

// App event handlers
app.whenReady().then(() => {
  createWindow()
  createMenu()

  startPythonSTTProcess()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// IPC handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion()
})

ipcMain.handle('get-platform', () => {
  return {
    platform: process.platform,
    arch: process.arch,
    version: process.getSystemVersion()
  }
})

ipcMain.handle('save-settings', async (event, settings) => {
  try {
    const settingsData = {
      ...settings,
      lastUpdated: new Date().toISOString()
    }
    
    await fs.writeFile(settingsPath, JSON.stringify(settingsData, null, 2))
    return { success: true }
  } catch (error) {
    console.error('Failed to save settings:', error)
    return { success: false, error: error.message }
  }
})

ipcMain.handle('load-settings', async () => {
  try {
    const data = await fs.readFile(settingsPath, 'utf8')
    return { success: true, settings: JSON.parse(data) }
  } catch (error) {
    if (error.code === 'ENOENT') {
      return { success: true, settings: null } // No settings file yet
    }
    console.error('Failed to load settings:', error)
    return { success: false, error: error.message }
  }
})

ipcMain.handle('show-save-dialog', async (event, options) => {
  const { dialog } = await import('electron')
  const result = await dialog.showSaveDialog(mainWindow, options)
  return result
})

ipcMain.handle('show-open-dialog', async (event, options) => {
  const { dialog } = await import('electron')
  const result = await dialog.showOpenDialog(mainWindow, options)
  return result
})

ipcMain.handle('send-python-command', (event, command, payload = {}) => {
  if (!pythonProcess) {
    console.error('Python process not running, cannot send command.')
    return { success: false, error: 'Python process not running' }
  }

  const message = JSON.stringify({ command, ...payload }) + '\n'
  pythonProcess.stdin.write(message)
  console.log(`Sent to Python: ${message.trim()}`)
  return { success: true }
})