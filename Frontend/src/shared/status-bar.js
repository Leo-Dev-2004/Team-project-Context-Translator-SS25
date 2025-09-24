import { LitElement, html, css } from 'lit';

export class StatusBar extends LitElement {
  static properties = {
    serverStatus: { type: String },
    microphoneStatus: { type: String }
  };

  static styles = css`
    :host {
      display: block;
      width: 100%;
    }

    .status-item {
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      font-size: 12px; 
    }
    
    .status-container {
      display: flex;
      justify-content: center;
      align-items: center;

      width: 330px;
      margin: 0 auto 20px auto;

      padding: 12px 24px;

      background: var(--md-sys-color-surface);
      border-radius: var(--radius-lg, 12px); /* 12px als Fallback-Wert */
      box-shadow: var(--shadow-lg);

      border: 1px solid var(--color-secondary); 
    
    }
    
    .status-content {
      display: flex;
      align-items: center;
      gap: 24px; /* Abstand zwischen den Statusanzeigen */
      padding: 0 16px;
    }
    
    .status-item {
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .status-label {
    /* Hält die Beschriftung lesbar und verhindert einen Zeilenumbruch */
    white-space: nowrap;
   }

    .status-value {
    /* Das ist der entscheidende Teil! */
    min-width: 85px;     /* Feste Mindestbreite, um Springen zu verhindern */
    text-align: left;    /* Stellt sicher, dass der Text linksbündig ist */
    white-space: nowrap; /* Verhindert Zeilenumbruch bei längeren Status */
    }
    
    .connected { background-color: #4caf50; }
    .muted { background-color: #2aa4b9ff; }
    .not-found { background-color: #e6dd59ff; }
    .trouble { background-color: #ff9800; }
    .denied { background-color: #f44336; }
    .disconnected { background-color: #cd1d10ff; }
    .initializing { background-color: #9e9e9e; }
  `;

  constructor() {
    super();
    this.serverStatus = 'initializing';
    this.microphoneStatus = 'initializing';
  }

  render() {
    return html`
    <div class="status-container">
      <div class="status-content">
        <div class="status-item server">
          <div class="status-indicator ${this.serverStatus}"></div>
          <span class="status-label">Server:</span>
          <span class="status-value">${this.serverStatus}</span>
        </div>
        <div class="status-item microphone">
          <div class="status-indicator ${this.microphoneStatus}"></div>
          <span class="status-label">Microphone:</span>
          <span class="status-value">${this.microphoneStatus}</span>
        </div>
      </div>
    </div>
  `;
  }
}
customElements.define('status-bar', StatusBar);