import { UI } from '../../shared/src/index.js';
import '../../shared/src/index.css';
import { initializeApplication } from '../../shared/app.js'; // Correct path to app.js

// Electron-enhanced element
class ElectronMyElement extends UI {
  constructor() {
    super();
    this.platform = 'electron';
    this.isElectron = true;
  }

  // Use firstUpdated for main application initialization
  async firstUpdated(changedProperties) {
    super.firstUpdated(changedProperties); // Call super.firstUpdated first

    // Call initializeApplication with 'this' (the instance of ElectronMyElement)
    // This ensures app.js gets the correct UI component reference.
    initializeApplication(this); // <--- THIS IS THE SOLE CALL NOW
    console.log('renderer.js: initializeApplication called after first render.');

    // Electron-specific initialization
    await this._initializeElectron();
  }

  // connectedCallback is still useful for handlers, but main app init is in firstUpdated
  async connectedCallback() {
    super.connectedCallback();
    this.saveSettingsHandler = this._saveSettings.bind(this);
    this.exportTranslationsHandler = this._exportTranslations.bind(this);
  }

  // ... (rest of ElectronMyElement methods) ...

  async _initializeElectron() {
    if (window.electronAPI) {
      try {
        const platformInfo = await window.electronAPI.getPlatform();
        console.log('Platform:', platformInfo);

        const result = await window.electronAPI.loadSettings();
        if (result.success && result.settings) {
          this._loadSettingsFromElectron(result.settings);
        }

        const version = await window.electronAPI.getAppVersion();
        console.log('App version:', version);

      } catch (error) {
        console.error('Electron initialization error:', error);
      }
    } else {
        console.warn('Electron API not available on window.electronAPI. Running in web mode fallback.');
    }
  }

  _loadSettingsFromElectron(settings) {
    this.domainValue = settings.domain || '';
    this.selectedLanguage = settings.language || 'en';
    this.autoSave = settings.autoSave || false;
    console.log('Settings loaded from Electron:', settings);
  }

  async _saveSettings() {
    const settings = {
      domain: this.domainValue,
      language: this.selectedLanguage,
      autoSave: this.autoSave,
      platform: this.platform,
      timestamp: new Date().toISOString()
    };

    if (window.electronAPI) {
      try {
        const result = await window.electronAPI.saveSettings(settings);
        if (result.success) {
          console.log('Settings saved via Electron API:', settings);
          this._showNotification('Settings saved to file system!');
        } else {
          console.error('Failed to save settings:', result.error);
          this._showNotification('Failed to save settings', 'error');
        }
      } catch (error) {
        console.error('Error saving settings:', error);
        this._showNotification('Error saving settings', 'error');
      }
    } else {
      try {
        localStorage.setItem('context-translator-settings', JSON.stringify(settings));
        console.log('Settings saved to localStorage (fallback):', settings);
        this._showNotification('Settings saved to localStorage!');
      } catch (error) {
        console.error('Error saving settings to localStorage:', error);
        this._showNotification('Error saving settings to localStorage', 'error');
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
      });

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
        };

        console.log('Export to:', result.filePath);
        console.log('Export data:', data);

        this._showNotification(`Export saved to ${result.filePath}`);
      }
    } else {
      super._exportTranslations();
    }
  }

  _showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
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
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 4000);
  }
}

if (!customElements.get('my-element')) {
  customElements.define('my-element', ElectronMyElement);
} else {
  console.warn('Attempted to define "my-element" again. Skipping.');
}
