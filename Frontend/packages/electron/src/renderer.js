import { UI } from '../../shared/src/index.js'
import '../../shared/src/index.css'

// Electron-enhanced element
class ElectronMyElement extends UI {
  constructor() {
    super()
    this.platform = 'electron'
    this.isElectron = true
    this.backendWs = null; // Property to hold the backend WebSocket connection
  }

  async connectedCallback() {
    super.connectedCallback()
    await this._initializeElectron()
    await this._runCommunicationTests(); // <<< New method to run all tests
  }

  async _initializeElectron() {
    if (window.Electron) {
      try {
        // Get platform info
        const platformInfo = await window.electronAPI.getPlatform()
        console.log('Platform:', platformInfo)
        
        // Load saved settings
        const result = await window.electronAPI.loadSettings()
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings)
        }
        
        // Get app version
        const version = await window.electronAPI.getAppVersion()
        console.log('App version:', version)
        
      } catch (error) {
        console.error('Electron initialization error:', error)
      }
    }
  }

  // <<< NEW METHOD: Centralized communication tests
  async _runCommunicationTests() {
    console.log('--- Starting Electron IPC Communication Tests ---');
    await this._testElectronIPC();
    console.log('--- Electron IPC Communication Tests Finished ---');

    console.log('--- Starting Backend WebSocket Communication Tests ---');
    await this._testBackendWebSocket();
    console.log('--- Backend WebSocket Communication Tests Finished ---');
  }

  // <<< NEW METHOD: Test Electron IPC (Renderer <-> Main)
  async _testElectronIPC() {
    if (!window.electronAPI) {
      console.warn('IPC Test: window.electronAPI not available. Skipping IPC tests.');
      return;
    }

    try {
      // Test 1: getAppVersion
      const version = await window.Electron.getAppVersion();
      console.log('IPC Test [1/4]: getAppVersion -> Success:', version);

      // Test 2: getPlatform
      const platformInfo = await window.electronAPI.getPlatform();
      console.log('IPC Test [2/4]: getPlatform -> Success:', platformInfo);

      // Test 3: saveSettings
      const dummySettings = { 
        testKey: 'testValueFromRenderer', 
        timestamp: new Date().toISOString(),
        source: 'renderer_ipc_test'
      };
      const saveResult = await window.electronAPI.saveSettings(dummySettings);
      if (saveResult.success) {
        console.log('IPC Test [3/4]: saveSettings -> Success. Check your .context-translator-settings.json');
      } else {
        console.error('IPC Test [3/4]: saveSettings -> Failed:', saveResult.error);
      }

      // Test 4: loadSettings (should load the dummy settings if saved)
      const loadedSettings = await window.electronAPI.loadSettings();
      if (loadedSettings.success && loadedSettings.settings) {
        console.log('IPC Test [4/4]: loadSettings -> Success. Loaded settings:', loadedSettings.settings);
      } else {
        console.warn('IPC Test [4/4]: loadSettings -> No settings or failed to load:', loadedSettings.error || 'No settings found');
      }

      // Optional: Test showSaveDialog - requires user interaction, might not be suitable for automated logs
      // console.log('IPC Test [Optional]: showSaveDialog...');
      // const saveDialogResult = await window.electronAPI.showSaveDialog({
      //   title: 'IPC Save Dialog Test',
      //   defaultPath: `ipc-dialog-test-${new Date().toISOString().split('T')[0]}.txt`
      // });
      // if (!saveDialogResult.canceled && saveDialogResult.filePath) {
      //   console.log('IPC Test [Optional]: Save dialog selected path:', saveDialogResult.filePath);
      // } else {
      //   console.log('IPC Test [Optional]: Save dialog canceled.');
      // }

    } catch (error) {
      console.error('IPC Test: An unexpected error occurred during IPC tests:', error);
    }
  }

  // <<< NEW METHOD: Test Backend WebSocket (Renderer <-> Python Backend)
  async _testBackendWebSocket() {
    const backendWsUrl = 'ws://localhost:8000/ws/frontend_client'; // Unique client ID for frontend

    // Close existing connection if any
    if (this.backendWs && this.backendWs.readyState === WebSocket.OPEN) {
      this.backendWs.close();
    }

    this.backendWs = new WebSocket(backendWsUrl);

    this.backendWs.onopen = (event) => {
      console.log('WebSocket Test: Connected to backend!');
      // Send an initial message from frontend to backend
      this.backendWs.send(JSON.stringify({
          id: crypto.randomUUID(),
          type: 'frontend.init',
          timestamp: Date.now() / 1000,
          payload: { message: 'Frontend connected to WebSocket' },
          origin: 'frontend_renderer',
          client_id: 'frontend_client'
      }));
      console.log('WebSocket Test: Sent initial message to backend.');
    };

    this.backendWs.onmessage = (event) => {
      console.log('WebSocket Test: Received message from backend:', event.data);
      try {
        const message = JSON.parse(event.data);
        // You should see 'stt.transcription' messages here if STT module is sending data
        if (message.type === 'stt.transcription') {
          console.log('WebSocket Test: Received Transcription:', message.payload.text);
          // Here you would typically update your UI with the transcribed text
        } else if (message.type === 'system.queue_status_update') {
          // These are frequent, might want to log less Verbose
          // console.log('WebSocket Test: Received Queue Status Update:', message.payload);
        } else {
          console.log('WebSocket Test: Received other message type:', message.type, message.payload);
        }
      } catch (e) {
        console.error('WebSocket Test: Error parsing message from backend:', e);
      }
    };

    this.backendWs.onclose = (event) => {
      console.warn('WebSocket Test: Disconnected from backend:', event.code, event.reason);
      // Simple reconnection logic for testing, consider exponential backoff for production
      if (this.isElectron) { // Only attempt reconnect if Electron app is still running
        console.log('WebSocket Test: Attempting to reconnect in 3 seconds...');
        setTimeout(() => this._testBackendWebSocket(), 3000); 
      }
    };

    this.backendWs.onerror = (error) => {
      console.error('WebSocket Test: Error:', error);
    };
  }
  // <<< END NEW METHODS


  _loadSettingsFromElectron(settings) {
    this.domainValue = settings.domain || ''
    this.selectedLanguage = settings.language || 'en'
    this.autoSave = settings.autoSave || false
    console.log('Settings loaded from Electron:', settings)
  }

  async _saveSettings() {
    const settings = {
      domain: this.domainValue,
      language: this.selectedLanguage,
      autoSave: this.autoSave,
      platform: this.platform,
      timestamp: new Date().toISOString()
    }

    if (window.electronAPI) {
      // Electron: Persistent file storage
      try {
        const result = await window.electronAPI.saveSettings(settings)
        if (result.success) {
          console.log('Settings saved via Electron API:', settings)
          this._showNotification('Settings saved to file system!')
        } else {
          console.error('Failed to save settings:', result.error)
          this._showNotification('Failed to save settings', 'error')
        }
      } catch (error) {
        console.error('Error saving settings:', error)
        this._showNotification('Error saving settings', 'error')
      }
    } else {
      // Fallback to localStorage
      try {
        localStorage.setItem('context-translator-settings', JSON.stringify(settings))
        console.log('Settings saved to localStorage (fallback):', settings)
        this._showNotification('Settings saved to localStorage!')
      } catch (error) {
        console.error('Error saving settings to localStorage:', error)
        this._showNotification('Error saving settings to localStorage', 'error')
      }
    }
  }

  // Override methods for Electron-specific features
  async _exportTranslations() {
    if (window.electronAPI) {
      const result = await window.electronAPI.showSaveDialog({
        title: 'Export Translations',
        defaultPath: `context-translator-export-${new Date().toISOString().split('T')[0]}.json`,
        filters: [
          { name: 'JSON Files', extensions: ['json'] },
          { name: 'All Files', extensions: ['*'] }
        ]
      })
      
      if (!result.canceled) {
        const data = {
          settings: {
            domain: this.domainValue,
            language: this.selectedLanguage,
            autoSave: this.autoSave
          },
          platform: 'electron',
          exportedAt: new Date().toISOString(),
          filePath: result.filePath
        }
        
        console.log('Export to:', result.filePath)
        console.log('Export data:', data)
        
        // In a real implementation, you would write the file here
        // For now, just show success
        this._showNotification(`Export saved to ${result.filePath}`)
      }
    } else {
      // Fallback to web behavior
      super._exportTranslations()
    }
  }

  _showNotification(message, type = 'success') {
    // Simple notification - in production you might use a toast library
    const notification = document.createElement('div')
    notification.textContent = message
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      border-radius: 8px;
      color: white;
      background-color: ${type === 'error' ? '#ef4444' : '#10b981'};
      z-index: 1000;
      font-family: var(--md-sys-typescale-body-large-font);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    `
    
    document.body.appendChild(notification)
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification)
      }
    }, 4000)
  }
}

// Register the Electron-enhanced element
if (!customElements.get('my-element')) {
  customElements.define('my-element', ElectronMyElement)
} else {
  console.warn("Custom element 'my-element' already defined. Skipping re-registration.")
}