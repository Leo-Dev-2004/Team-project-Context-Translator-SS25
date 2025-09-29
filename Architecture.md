# 🏛️ Projekt-Architektur: Real-time Contextual Assistant

## 🌟 Überblick

Der **Real-time Contextual Assistant** ist ein KI-gestützter Desktop-Assistent, der in Echtzeit kontextbezogene Erklärungen während Live-Gesprächen liefert. Das System basiert auf einer modernen, serviceorientierten Architektur, die für hochleistungsfähige Echtzeit-KI-Verarbeitung ausgelegt ist.

### Kernfunktionalitäten
- **Echtzeit-Spracherkennung**: Kontinuierliche Erfassung und Umwandlung von Mikrofon-Audio zu Text
- **KI-gestützte Terminologie-Erkennung**: Automatische Identifikation komplexer Fachbegriffe
- **Sofortige Kontextualisierung**: Generierung prägnanter Erklärungen für erkannte Begriffe
- **Desktop-Integration**: Native Electron-Anwendung mit benutzerfreundlicher Oberfläche

## 🏗️ System-Architektur

Die Anwendung besteht aus vier unabhängigen Hauptkomponenten, die über WebSockets in Echtzeit kommunizieren:

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   System Runner     │    │   STT-Modul        │    │   Backend (FastAPI) │
│   (Master-Skript)   │    │   (Speech-to-Text) │    │   (Zentrale Logik)  │
│                     │    │                     │    │                     │
│ • Prozessüberwachung│    │ • Audio-Erfassung   │    │ • Client-Management │
│ • Service-Koordin.  │    │ • Whisper-STT       │    │ • Message-Routing   │
│ • Lifecycle-Mgmt.   │    │ • Echtzeit-Stream   │    │ • KI-Pipeline       │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
            │                          │                          │
            └──────── WebSocket ────────┼──────── WebSocket ──────┘
                                       │
                    ┌─────────────────────┐
                    │ Frontend (Electron) │
                    │  (Desktop-GUI)      │
                    │                     │
                    │ • UI-Komponenten    │
                    │ • Session-Mgmt.     │
                    │ • Explanation-View  │
                    └─────────────────────┘
```

### 1. System Runner (`SystemRunner.py`)
**Rolle**: Master-Koordinator für alle Systemkomponenten
- **Prozess-Management**: Startet, überwacht und beendet alle anderen Services
- **Koordination**: Stellt sicher, dass Backend, STT-Modul und Frontend ordnungsgemäß initialisiert werden
- **Fehlerbehandlung**: Überwachung der Service-Gesundheit und automatisches Neustarten bei Bedarf
- **Session-Management**: Generiert eindeutige User-Session-IDs für die Sitzungsverfolgung

### 2. STT-Modul (`Backend/STT/`)
**Rolle**: Hochleistungs-Spracherkennung
- **Audio-Pipeline**: Kontinuierliche Mikrofon-Erfassung mit optimierter Pufferung
- **Whisper-Integration**: Verwendung von faster-whisper für präzise Speech-to-Text-Umwandlung
- **Streaming-Optimierung**: Chunk-basierte Verarbeitung für minimale Latenz
- **WebSocket-Kommunikation**: Direkter Stream von Transkriptionen zum Backend

### 3. Backend (`Backend/backend.py`)
**Rolle**: Zentrale Intelligenz und Orchestrierung
- **FastAPI-Server**: Asynchrone HTTP/WebSocket-API auf Port 8000
- **Message-Routing**: Intelligente Weiterleitung zwischen Services über `MessageRouter`
- **KI-Pipeline**: Zweistufige AI-Verarbeitung (SmallModel → MainModel)
- **Client-Management**: Multi-Client-Unterstützung mit Session-Isolation
- **Settings-Management**: Zentralisierte Konfigurationsverwaltung

#### Backend-Kernkomponenten

##### Message Queue System
```python
# Zentrale Queue-Architektur
queues = {
    'incoming': MessageQueue(),      # STT → Backend
    'detection': MessageQueue(),     # Backend → SmallModel  
    'main_model': MessageQueue(),    # SmallModel → MainModel
    'websocket_out': MessageQueue()  # MainModel → Frontend
}
```

##### Zweistufige KI-Verarbeitung
1. **SmallModel** (`Backend/models/SmallModel.py`)
   - Schnelle Terminologie-Erkennung mit Ollama
   - Domain-spezifische Filterung basierend auf User-Settings
   - Lightweight-Modell für Echtzeit-Performance

2. **MainModel** (`Backend/models/MainModel.py`)
   - Detaillierte Erklärungsgenerierung 
   - Kontextbewusste Prompt-Konstruktion
   - Integration mit globalen Settings (Domain, Erklärungsstil)

### 4. Frontend (`Frontend/`)
**Rolle**: Desktop-UI und User-Interaktion
- **Electron-App**: Cross-Platform Desktop-Anwendung
- **WebSocket-Client**: Echtzeit-Verbindung zum Backend (ws://localhost:8000)
- **Lit-Komponenten**: Moderne Web-Components für reactive UI
- **Explanation-Management**: Lokale Speicherung und Darstellung von KI-Erklärungen

## 🔄 Datenfluss und Interaktionen

### Hauptdatenfluss: Audio → Erklärung
```
1. Mikrofon-Audio
   │
   ▼
2. STT-Modul (Whisper)
   │ (WebSocket)
   ▼
3. Backend Message-Router
   │
   ▼
4. SmallModel (Terminologie-Erkennung)
   │
   ▼
5. MainModel (Erklärungsgenerierung)
   │ (WebSocket)
   ▼
6. Frontend (UI-Darstellung)
```

### Settings-Synchronisation
Das System implementiert eine bidirektionale Settings-Synchronisation zwischen Frontend und Backend:

1. **Frontend → Backend**: User-Änderungen werden via WebSocket übertragen
2. **Backend-Persistierung**: Settings werden in `Backend/settings.json` gespeichert
3. **AI-Integration**: SmallModel und MainModel konsumieren Settings für kontextuelle Verarbeitung

### Session-Management
- **Session-Erstellung**: User kann neue Sessions starten oder bestehende beitreten
- **Client-Isolation**: Jede Session hat isolierte Message-Queues und Explanation-Stores
- **Multi-User-Support**: Backend unterstützt multiple gleichzeitige Sessions

## 💻 Frontend-Architektur (Electron)

### Komponenten-Hierarchie
```
src/
├── main.js              # Electron Main Process
├── preload.js           # Secure API Bridge (CommonJS)
├── renderer.js          # Renderer Entry + WebSocket Logic
└── shared/              # Geteilte UI-Komponenten
    ├── ui.js            # Basis-UI-Komponente
    ├── explanation-manager.js    # Zentraler Store
    ├── universal-message-parser.js # Message-Parsing
    ├── explanation-item.js       # Einzelne Erklärung
    └── styles.js        # Style-System
```

### Technologie-Stack
- **Electron**: Native Desktop-Integration
- **Lit**: Reactive Web Components
- **Vite**: Moderne Build-Pipeline für Renderer
- **esbuild**: Preload-Script-Bundling
- **Material Web**: M3-konforme UI-Komponenten

### Sicherheitsmodell
- **Sandbox**: Renderer läuft in eingeschränkter Umgebung
- **Preload-Bridge**: Minimale, sichere API-Oberfläche
- **CSP**: Content Security Policy für localhost:5174 und :8000
- **IPC**: Sichere Kommunikation zwischen Main und Renderer

### Message-Protokoll
Alle WebSocket-Nachrichten folgen einem einheitlichen Schema:
```typescript
interface UniversalMessage {
  id: string
  type: string
  timestamp: number  // sec oder ms
  payload: any
  client_id: string
  origin: string
  destination: string
}
```

#### Wichtige Message-Types
- `session.start` / `session.join`: Session-Management
- `stt.transcript`: Transkriptions-Updates vom STT-Modul
- `explanation.generated`: Neue KI-Erklärungen
- `settings.save`: Settings-Synchronisation
- `manual.request`: Manuelle Erklärungsanfragen

## 🛠️ Entwicklung und Deployment

### Entwicklungsumgebung
```bash
# Backend starten
python -m uvicorn Backend.backend:app --host 0.0.0.0 --port 8000

# Frontend entwickeln (aus Frontend/)  
npm run dev

# Komplettes System
python SystemRunner.py
```

### Build-Pipeline
- **Frontend**: `npm run build` (Vite + electron-builder)
- **Backend**: Python-Module mit requirements.txt
- **Distribution**: Electron-App-Pakete für Windows/Mac/Linux

### Konfiguration
- **Backend-Settings**: `Backend/settings.json`
- **Frontend-Settings**: `~/.context-translator-settings.json` (via Electron)
- **Environment**: `.env` für entwicklungsspezifische Konfiguration

### Logging und Monitoring
- **Zentralisiertes Logging**: Alle Komponenten loggen strukturiert
- **Prozess-Überwachung**: SystemRunner überwacht Service-Gesundheit
- **Performance-Metriken**: Queue-Status und Verarbeitungszeiten

## 🔧 Wichtige Design-Prinzipien

### Lose Kopplung
- Services kommunizieren ausschließlich über definierte Schnittstellen
- Jede Komponente kann unabhängig entwickelt und getestet werden
- Queue-basierte Architektur ermöglicht asynchrone Verarbeitung

### Skalierbarkeit
- Message-Queue-System unterstützt horizontale Skalierung
- Modular aufgebaute AI-Pipeline ermöglicht Model-Swapping
- Session-basierte Architektur für Multi-User-Szenarien

### Performance-Optimierung
- Streaming STT für minimale Audio-Latenz
- In-Memory-Caching für Settings und Sessions
- Asynchrone Verarbeitung an allen kritischen Punkten

### Benutzerfreundlichkeit
- Native Desktop-Integration über Electron
- Responsive UI mit sofortiger Feedback-Anzeige
- Persistente lokale Einstellungen und Explanation-Historie

---

*Dieses Architektur-Dokument wird kontinuierlich aktualisiert, um die Weiterentwicklung des Systems zu reflektieren.*