import { UI } from '../../shared/src/index.js'
import '../../shared/src/index.css'

// Web-spezifische Erweiterungen
class WebMyElement extends UI {
  constructor() {
    super()
    this.platform = 'web'
    this.hasGoogleMeet = !!window.meet
  }

  connectedCallback() {
    super.connectedCallback()
    this._initializeGoogleMeet()
  }

  async _initializeGoogleMeet() {
    if (this.hasGoogleMeet) {
      try {
        // Google Meet Add-on Integration
        const { meet } = await import('@googleworkspace/meet-addons')
        console.log('Google Meet Add-on initialized')
        // Add Meet-specific functionality here
      } catch (error) {
        console.log('Google Meet not available:', error)
      }
    }
  }

  async _saveSettings() {
    const settings = {
      domain: this.domainValue,
      language: this.selectedLanguage,
      autoSave: this.autoSave,
      platform: this.platform,
      timestamp: new Date().toISOString()
    }

    // Web: localStorage
    try {
      localStorage.setItem('context-translator-settings', JSON.stringify(settings))
      console.log('Settings saved to localStorage:', settings)
      
      // Show success feedback
      this._showNotification('Settings saved successfully!')
    } catch (error) {
      console.error('Failed to save settings:', error)
      this._showNotification('Failed to save settings', 'error')
    }
  }

  _loadSettings() {
    try {
      const saved = localStorage.getItem('context-translator-settings')
      if (saved) {
        const settings = JSON.parse(saved)
        this.domainValue = settings.domain || ''
        this.selectedLanguage = settings.language || 'en'
        this.autoSave = settings.autoSave || false
        console.log('Settings loaded from localStorage:', settings)
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  async _exportTranslations() {
    const data = {
      settings: {
        domain: this.domainValue,
        language: this.selectedLanguage,
        autoSave: this.autoSave
      },
      platform: 'web',
      exportedAt: new Date().toISOString()
    }

    // Web: Download as file
    const blob = new Blob([JSON.stringify(data, null, 2)], { 
      type: 'application/json' 
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `context-translator-export-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    this._showNotification('Export downloaded successfully!')
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
    `
    
    document.body.appendChild(notification)
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification)
      }
    }, 3000)
  }
}

// Register the web-enhanced element
customElements.define('my-element', WebMyElement)