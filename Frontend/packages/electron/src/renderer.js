// renderer.js (Vollständige Implementierung)

import { UI } from '../../shared/src/index.js';
import '../../shared/src/index.css';

class ElectronMyElement extends UI {
  constructor() {
    super();
    this.platform = 'electron';
    this.isElectron = true;
    this.backendWs = null;
    console.log('Renderer: ⚙️ ElectronMyElement constructor called.');
  }

  _startSession() {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('Keine Verbindung zum Backend', 'error');
    }
    console.log('Renderer: Sende "session.start"-Anfrage...');
    const message = {
      id: crypto.randomUUID(),
      type: 'session.start',
      payload: {},
    };
    this.backendWs.send(JSON.stringify(message));
  }

  _joinSession() {
    const codeInput = this.shadowRoot.querySelector('#session-code-input');
    const code = codeInput ? codeInput.value : '';

    if (!code) {
      return this._showNotification('Bitte einen Session-Code eingeben', 'error');
    }
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      return this._showNotification('Keine Verbindung zum Backend', 'error');
    }
    
    console.log(`Renderer: Sende "session.join"-Anfrage mit Code ${code}...`);
    const message = {
      id: crypto.randomUUID(),
      type: 'session.join',
      payload: { code: code },
    };
    this.backendWs.send(JSON.stringify(message));
  }


  /**
   * Baut die WebSocket-Verbindung zum Backend auf und richtet die Event-Listener ein.
   */
  _initializeWebSocket() {
    const clientId = `frontend_renderer_${crypto.randomUUID()}`;
    const wsUrl = `ws://localhost:8000/ws/${clientId}`;
    console.log(`Renderer: ⚙️ Versuche, WebSocket-Verbindung zu ${wsUrl} aufzubauen...`);

    if (this.backendWs) {
      this.backendWs.close();
    }
    
    this.backendWs = new WebSocket(wsUrl);

    this.backendWs.onopen = (event) => {
      console.log('Renderer: ✅ WebSocket-Verbindung zum Backend erfolgreich hergestellt.');
    };

    this.backendWs.onmessage = (event) => {
      console.log(`Renderer: 💡 Nachricht vom Backend empfangen:`, event.data);
      try {
        const message = JSON.parse(event.data);
        
        // Hier die Logik zur Verarbeitung von Nachrichten vom Backend
        if (message.type === 'translation.result') {
          this.addTranslation(message.payload); // Annahme: Methode aus der 'UI'-Basisklasse
        } else if (message.type === 'stt.transcription') {
          this.addTranscription(message.payload); // Annahme: Methode aus der 'UI'-Basisklasse
        }
      } catch (error) {
        console.error('Renderer: ❌ Fehler beim Parsen der Backend-Nachricht:', error);
      }
    };

    this.backendWs.onerror = (error) => {
      console.error('Renderer: ❌ WebSocket-Fehler:', error);
      this._showNotification('WebSocket-Verbindung fehlgeschlagen', 'error');
    };

    this.backendWs.onclose = (event) => {
      console.log('Renderer: ⚙️ WebSocket-Verbindung geschlossen.', `Code: ${event.code}`, `Grund: ${event.reason}`);
      this.backendWs = null;
      // Optional: Logik für einen automatischen Wiederverbindungsversuch
      // setTimeout(() => this._initializeWebSocket(), 5000);
    };
  }

  /**
   * Sendet eine Demo-Nachricht an das Backend.
   * @param {string} text Der zu sendende Text
   */
  sendDemoSTTMessage(text) {
    if (!this.backendWs || this.backendWs.readyState !== WebSocket.OPEN) {
      console.error('Renderer: ❌ WebSocket ist nicht verbunden. Kann Nachricht nicht senden.');
      this._showNotification('Keine Verbindung zum Backend', 'error');
      return;
    }

    const clientId = this.backendWs.url.split('/').pop();
    const message = {
      id: crypto.randomUUID(),
      // Hinweis: 'stt.transcription' simuliert hier eine Nachricht, die normalerweise
      // vom STT-Modul käme. Für echte Aktionen vom Frontend wären andere Typen
      // wie 'simulation.start' oder 'user.input' besser geeignet.
      type: 'stt.transcription',
      timestamp: Date.now() / 1000,
      payload: {
        text: text,
        language: 'de',
        confidence: 0.99
      },
      origin: 'frontend_renderer',
      client_id: clientId
    };

    this.backendWs.send(JSON.stringify(message));
    console.log(`Renderer: 💡 Demo-Nachricht an Backend gesendet: ${text}`);
  }

  /**
   * Wird aufgerufen, wenn das Element in das DOM eingefügt wird.
   * Initialisiert die gesamte Anwendungslogik.
   */
  async connectedCallback() {
    console.log('Renderer: ⚙️ connectedCallback entered.');
    super.connectedCallback();
    console.log('Renderer: ✅ super.connectedCallback() completed.');

    // Initialisiert Electron-spezifische APIs und lädt Einstellungen
    await this._initializeElectron();
    
    // Baut die WebSocket-Verbindung zum Backend auf
    this._initializeWebSocket();
    
    // Führt initiale Kommunikationstests durch
    await this._runCommunicationTests();
    
    // Fügt den Demo-Button zur UI hinzu
    this._attachDemoButton();
    
    console.log('Renderer: ⚙️ connectedCallback exited.');
  }
  
  /**
   * Initialisiert die Electron-Schnittstelle und lädt gespeicherte Einstellungen.
   */
  async _initializeElectron() {
    console.log('Renderer: ⚙️ _initializeElectron entered.');
    if (window.electronAPI) {
      console.log('Renderer: ✅ window.electronAPI ist verfügbar.');
      try {
        const platformInfo = await window.electronAPI.getPlatform();
        console.log('Renderer: ✅ Platform-Info geladen:', platformInfo);
        
        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings);
          console.log('Renderer: ✅ Einstellungen via Electron geladen.');
        } else if (!result.success) {
           console.error('Renderer: ❌ Fehler beim Laden der Einstellungen:', result.error);
        }
      } catch (error) {
        console.error('Renderer: ❌ Fehler bei der Electron-Initialisierung:', error);
      }
    } else {
        console.warn('Renderer: ⚠️ window.electronAPI nicht gefunden. Läuft nicht in Electron?');
    }
  }

  /**
   * Fügt den Demo-Button zum Testen der Nachrichtenübertragung hinzu.
   */
  _attachDemoButton() {
    console.log('Renderer: 💡 Hänge Demo-Button an die UI an...');
    const buttonContainer = this.shadowRoot.querySelector('div.action-buttons');
    
    if (buttonContainer) {
      const demoButton = document.createElement('md-filled-button');
      demoButton.textContent = 'Sende Demo-Nachricht';
      demoButton.id = 'send-demo-button';
      demoButton.style.cssText = `margin-left: 10px;`;
      
      demoButton.addEventListener('click', () => {
        console.log('Renderer: 🚀 Demo-Button geklickt.');
        this.sendDemoSTTMessage('Das ist eine manuell ausgelöste Testnachricht aus dem Frontend.');
      });

      buttonContainer.appendChild(demoButton);
      console.log('Renderer: ✅ Demo-Button erfolgreich angehängt.');
    } else {
      console.error('Renderer: ❌ Button-Container mit Klasse "action-buttons" nicht im Shadow DOM gefunden.');
    }
  }

  /**
   * Führt eine Reihe von Selbsttests für die Kommunikation durch.
   */
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

  /**
   * Testet die grundlegende IPC-Kommunikation mit dem Electron Main-Prozess.
   */
  async _testElectronIPC() {
    try {
      const version = await window.electronAPI.getAppVersion();
      console.log(`[IPC Test] App Version: ${version} (OK)`);
      const platform = await window.electronAPI.getPlatform();
      console.log(`[IPC Test] Platform: ${platform.platform} (OK)`);
    } catch (e) {
      console.error('[IPC Test] Failed:', e);
    }
  }

  /**
   * Testet die WebSocket-Verbindung, indem auf eine offene Verbindung gewartet wird.
   */
  async _testBackendWebSocket() {
    return new Promise((resolve, reject) => {
      const timeout = 5000;
      const start = Date.now();
      const interval = setInterval(() => {
        if (this.backendWs && this.backendWs.readyState === WebSocket.OPEN) {
          clearInterval(interval);
          console.log('[WS Test] Connection is open. (OK)');
          resolve();
        } else if (Date.now() - start > timeout) {
          clearInterval(interval);
          console.error('[WS Test] Timeout: Connection was not open within 5s.');
          reject(new Error('WebSocket connection timeout'));
        }
      }, 100);
    });
  }

  /**
   * Wendet geladene Einstellungen auf die UI an.
   */
  _loadSettingsFromElectron(settings) {
    console.log('Renderer: Wende geladene Einstellungen an:', settings);
    // Annahme: Es gibt eine Methode in der Basisklasse `UI` zum Anwenden der Einstellungen
    // this.applySettings(settings); 
  }

  /**
   * Speichert die aktuellen UI-Einstellungen über die Electron-API.
   */
  async _saveSettings() {
    // Annahme: Es gibt eine Methode zum Sammeln der aktuellen Einstellungen
    // const currentSettings = this.collectSettings();
    const currentSettings = { theme: 'dark', language: 'de' }; // Beispiel-Daten
    console.log('Renderer: Speichere Einstellungen...', currentSettings);
    const result = await window.electronAPI.saveSettings(currentSettings);
    if (result.success) {
      this._showNotification('Einstellungen gespeichert', 'success');
    } else {
      this._showNotification(`Fehler beim Speichern: ${result.error}`, 'error');
    }
  }

  /**
   * Öffnet einen Speichern-Dialog und exportiert Übersetzungen.
   */
  async _exportTranslations() {
    const result = await window.electronAPI.showSaveDialog({
      title: 'Übersetzungen exportieren',
      defaultPath: 'translations.json',
      filters: [{ name: 'JSON Files', extensions: ['json'] }]
    });

    if (!result.canceled && result.filePath) {
      console.log(`Renderer: Exportiere nach ${result.filePath}`);
      // Hier würde die Logik zum Sammeln und Speichern der Daten folgen.
      // const dataToSave = JSON.stringify(this.translations, null, 2);
      // await window.electronAPI.saveFile(result.filePath, dataToSave);
      this._showNotification('Export erfolgreich (simuliert)', 'success');
    }
  }
  
  /**
   * Zeigt eine kurze Benachrichtigung in der UI an.
   */
  _showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      padding: 10px 20px;
      border-radius: 5px;
      color: white;
      background-color: ${type === 'error' ? '#D32F2F' : '#388E3C'};
      z-index: 1000;
      box-shadow: 0 2px 5px rgba(0,0,0,0.2);
      transition: opacity 0.5s;
    `;
    this.shadowRoot.appendChild(notification);
    setTimeout(() => {
      notification.style.opacity = '0';
      setTimeout(() => notification.remove(), 500);
    }, 3000);
  }
}

if (!customElements.get('my-element')) {
  window.customElements.define('my-element', ElectronMyElement);
} else {
  console.warn("Renderer: Custom element 'my-element' bereits definiert. Überspringe Neuregistrierung.");
}