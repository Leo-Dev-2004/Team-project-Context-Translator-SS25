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

    // Rufe die Initialisierung auf
    await this._initializeElectron();
    
    // Test-Logik für den automatischen Test-Runner
    await this._runCommunicationTests();
    
    console.log('Renderer: 💡 Attaching demo button...');
    
    // Prüfe den Shadow DOM auf den Button-Container
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

      console.log('Renderer: 💡 Attaching event listener to demo button.');
      demoButton.addEventListener('click', () => {
        console.log('Renderer: 🚀 Demo-Button geklickt. Sende Demo-Nachricht...');
        this.sendDemoSTTMessage('Das ist eine manuell ausgelöste Testnachricht aus dem Frontend.');
      });
      console.log('Renderer: ✅ Event listener attached.');
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
        const platformInfo = await window.Electron.getPlatform()
        console.log('Renderer: ✅ Platform info loaded:', platformInfo);
        
        const result = await window.Electron.loadSettings()
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings);
          console.log('Renderer: ✅ Settings loaded from Electron.');
        } else {
          console.warn('Renderer: ⚠️ No settings found or failed to load.');
        }
        
        const version = await window.Electron.getAppVersion()
        console.log('Renderer: ✅ App version:', version);
        
      } catch (error) {
        console.error('Renderer: ❌ Electron initialization error:', error);
      }
    }
    console.log('Renderer: ⚙️ _initializeElectron exited.');
  }

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

  async _testElectronIPC() { /* ... unverändert ... */ }
  async _testBackendWebSocket() { /* ... unverändert ... */ }
  _loadSettingsFromElectron(settings) { /* ... unverändert ... */ }
  async _saveSettings() { /* ... unverändert ... */ }
  async _exportTranslations() { /* ... unverändert ... */ }
  _showNotification(message, type = 'success') { /* ... unverändert ... */ }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement)
} else {
  console.warn("Renderer: Custom element 'my-element' already defined. Skipping re-registration.");
}