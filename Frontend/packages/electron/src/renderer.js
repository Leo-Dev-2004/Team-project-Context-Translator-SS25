import { UI } from '../../shared/src/index.js'
import '../../shared/src/index.css'

class ElectronMyElement extends UI {
  constructor() {
    super()
    this.platform = 'electron'
    this.isElectron = true
    this.backendWs = null;
    console.log('Renderer: ⚙️ ElectronMyElement constructor called.');
  }

  sendDemoSTTMessage(text) {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      console.error('Renderer: ❌ WebSocket is not connected. Cannot send message.');
      return;
    }
    const message = {
      id: crypto.randomUUID(),
      type: 'stt.transcription',
      timestamp: Date.now() / 1000,
      payload: {
        text: text,
        language: 'de',
        confidence: 0.69
      },
      origin: 'stt_module',
      client_id: 'frontend_renderer'
    };

    this.backendWs.send(JSON.stringify(message));
    console.log(`Renderer: 💡 Demo-Nachricht gesendet: ${text}`);
  }

  async connectedCallback() {
    console.log('Renderer: ⚙️ connectedCallback entered.');
    super.connectedCallback();
    console.log('Renderer: ✅ super.connectedCallback() completed.');

    await this._initializeElectron();

    // Automatische Tests vorerst entfernen, um sicherzustellen, dass sie die UI-Initialisierung nicht blockieren.
    // await this._runCommunicationTests();
    // console.log('Renderer: ✅ Test suite completed.');

    console.log('Renderer: 💡 Attaching demo button...');
    const buttonContainer = this.shadowRoot.querySelector('div.action-buttons');
    
    if (buttonContainer) {
      console.log('Renderer: ✅ Button container found. Creating button.');
      const demoButton = document.createElement('md-filled-button');
      demoButton.textContent = 'Sende Demo-Nachricht';
      demoButton.id = 'send-demo-button';
      demoButton.value = '';
      
      demoButton.style.cssText = `
        margin-left: 10px;
      `;
      buttonContainer.appendChild(demoButton);

      demoButton.addEventListener('click', () => {
        console.log('Renderer: 🚀 Demo-Button geklickt. Sende Demo-Nachricht...');
        this.sendDemoSTTMessage('Das ist eine manuell ausgelöste Testnachricht aus dem Frontend.');
      });
    } else {
      console.error('Renderer: ❌ Button-Container with class "action-buttons" not found in the Shadow DOM.');
    }
    
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }

  async _initializeElectron() {
    console.log('Renderer: ⚙️ _initializeElectron entered.');
    if (window.Electron) {
      console.log('Renderer: ✅ window.electronAPI is available.');
      try {
        const platformInfo = await window.Electron.getPlatform();
        console.log('Renderer: ✅ Platform info loaded:', platformInfo);
        
        const result = await window.Electron.loadSettings();
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings);
          console.log('Renderer: ✅ Settings loaded from Electron.');
        } else {
          console.warn('Renderer: ⚠️ No settings found or failed to load.');
        }
        
        const version = await window.Electron.getAppVersion();
        console.log('Renderer: ✅ App version:', version);
        
      } catch (error) {
        console.error('Renderer: ❌ Electron initialization error:', error);
      }
    }
  }

  // Hier können wir die automatische Test-Logik für später belassen
  async _runCommunicationTests() {
    console.log('Renderer: --- Starting Electron IPC Communication Tests ---');
    await this._testElectronIPC();
    console.log('Renderer: --- Electron IPC Communication Tests Finished ---');

    console.log('Renderer: --- Starting Backend WebSocket Communication Tests ---');
    try {
        await this._testBackendWebSocket();
        console.log('Renderer: --- Backend WebSocket Communication Tests Finished ---');
    } catch (error) {
        console.error('Renderer: --- Backend WebSocket Communication Tests Failed ---', error);
    }
  }

  async _testElectronIPC() {
    if (!window.Electron) {
      console.warn('IPC Test: window.electronAPI not available. Skipping IPC tests.');
      return;
    }

    try {
      const version = await window.Electron.getAppVersion();
      console.log('IPC Test [1/4]: getAppVersion -> Success:', version);

      const platformInfo = await window.electronAPI.getPlatform();
      console.log('IPC Test [2/4]: getPlatform -> Success:', platformInfo);

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

      const loadedSettings = await window.Electron.loadSettings();
      if (loadedSettings.success && loadedSettings.settings) {
        console.log('IPC Test [4/4]: loadSettings -> Success. Loaded settings:', loadedSettings.settings);
      } else {
        console.warn('IPC Test [4/4]: loadSettings -> No settings or failed to load:', loadedSettings.error || 'No settings found');
      }
    } catch (error) {
      console.error('IPC Test: An unexpected error occurred during IPC tests:', error);
    }
  }

  async _testBackendWebSocket() {
    return new Promise((resolve, reject) => {
      const backendWsUrl = 'ws://localhost:8000/ws/frontend_client';
      const testTimeout = 10000; 

      if (this.backendWs && this.backendWs.readyState === WebSocket.OPEN) {
        this.backendWs.close();
      }

      this.backendWs = new WebSocket(backendWsUrl);

      const timeoutId = setTimeout(() => {
        if (this.backendWs.readyState !== WebSocket.CLOSED) {
          this.backendWs.close();
        }
        reject(new Error('WebSocket Test: Timeout while waiting for test completion.'));
      }, testTimeout);

      this.backendWs.onopen = (event) => {
        console.log('WebSocket Test: Connected to backend!');
        this.backendWs.send(JSON.stringify({
            id: crypto.randomUUID(),
            type: 'frontend.init',
            timestamp: Date.now() / 1000,
            payload: { message: 'Frontend connected to WebSocket' },
            origin: 'frontend_renderer',
            client_id: 'frontend_client'
        }));
        console.log('WebSocket Test: Sent initial message to backend.');

        setTimeout(() => {
          console.log('WebSocket Test: Assuming test successful after sending message.');
          if (this.backendWs.readyState !== WebSocket.CLOSED) {
            this.backendWs.close();
          }
          clearTimeout(timeoutId);
          resolve();
        }, 2000);
      };

      this.backendWs.onmessage = (event) => {
        console.log('WebSocket Test: Received message from backend:', event.data);
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'stt.transcription') {
            console.log('WebSocket Test: Received Transcription:', message.payload.text);
          } else if (message.type === 'system.queue_status_update') {
            // Log less Verbose, da die Nachricht häufig gesendet wird.
          } else {
            console.log('WebSocket Test: Received other message type:', message.type, message.payload);
          }
        } catch (e) {
          console.error('WebSocket Test: Error parsing message from backend:', e);
        }
      };

      this.backendWs.onclose = (event) => {
        if (event.code !== 1000) {
          console.warn('WebSocket Test: Disconnected from backend:', event.code, event.reason);
          reject(new Error(`WebSocket Test: Connection closed unexpectedly with code ${event.code}`));
        } else {
           console.log('WebSocket Test: Connection closed cleanly.');
        }
      };

      this.backendWs.onerror = (error) => {
        console.error('WebSocket Test: Error:', error);
        if (this.backendWs.readyState !== WebSocket.CLOSED) {
            this.backendWs.close();
        }
        reject(error);
      };
    });
  }

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

    if (window.Electron) {
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
        
        this._showNotification(`Export saved to ${result.filePath}`)
      }
    } else {
      super._exportTranslations()
    }
  }

  _showNotification(message, type = 'success') {
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