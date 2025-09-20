import { LitElement, html, css } from 'lit';

export class StatusBar extends LitElement {
  static properties = {
    backendStatus: { type: String },
    microphoneStatus: { type: String }
  };

  static styles = css`
    :host {
      display: block;
      width: 100%;
      margin: 0;
      overflow-x: hidden;
    }
    
    .status-container {
      display: flex;
      width: 100vw;
      justify-content: center;
      padding: 12px 0;
      position: relative;
      left: 25%;
      right: 75%;
      margin-left: 0;
      margin-right: 0;
      border: 1px solid #003366; /* Dünne dunkelblaue Linie */
    }
    
    .status-content {
      display: flex;
      width: 100%;
      padding: 0 16px;
      position: relative;
    }
    
    .status-item {
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      position: absolute;
      transform: translateX(-50%);
    }
    
    .status-item.backend {
      left: 25%; /* Zentriert bei 1/4 der Fensterbreite */
    }
    
    .status-item.microphone {
      left: 75%; /* Zentriert bei 3/4 der Fensterbreite */
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    
    .connected { background-color: #4caf50; }
    .disconnected { background-color: #f44336; }
    .trouble { background-color: #ff9800; }
  `;

  constructor() {
    super();
    this.backendStatus = 'disconnected';
    this.microphoneStatus = 'disconnected';
  }

  render() {
    return html`
      <div class="status-container">
        <div class="status-content">
          <div class="status-item backend">
            <div class="status-indicator ${this.backendStatus}"></div>
            <span>Backend: ${this.backendStatus}</span>
          </div>
          <div class="status-item microphone">
            <div class="status-indicator ${this.microphoneStatus}"></div>
            <span>Microphone: ${this.microphoneStatus}</span>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('status-bar', StatusBar);