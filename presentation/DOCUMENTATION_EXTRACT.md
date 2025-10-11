# Information Extracted from Project Documentation
## For CS Doctorand Presentation

This document consolidates all relevant information from the project's .MD files for the presentation.

---

## From Architecture.md

### System Overview
- **Project Name**: Real-time Contextual Assistant
- **Purpose**: AI-powered desktop assistant delivering context-aware explanations during live conversations
- **Core Functionality**: Real-time speech recognition, AI-powered terminology detection, instant contextualization

### Core Components

#### 1. SystemRunner (SystemRunner.py)
**Role**: Master coordinator for all system components
- Process management: Starts, monitors, and terminates all services
- Coordination: Ensures Backend, STT-Modul, and Frontend are properly initialized
- Error handling: Health monitoring and automatic restart on failure
- Session management: Generates unique user-session IDs

#### 2. STT Module (Backend/STT/)
**Role**: High-performance speech recognition
- **Technology**: faster-whisper for precise speech-to-text conversion
- Audio pipeline: Continuous microphone capture with optimized buffering
- Streaming optimization: Chunk-based processing for minimal latency
- WebSocket communication: Direct stream of transcriptions to backend

**Performance**:
- <200ms audio processing latency
- Streaming transcription with interim results
- 67% faster first result for long speech (see STT_STREAMING_OPTIMIZATION.md)

#### 3. Backend (Backend/backend.py)
**Role**: Central intelligence and orchestration
- **Framework**: FastAPI async HTTP/WebSocket API on port 8000
- **Message routing**: Intelligent forwarding via MessageRouter
- **AI pipeline**: Two-stage processing (SmallModel → MainModel)
- **Client management**: Multi-client support with session isolation
- **Settings management**: Centralized configuration

**Queue Architecture**:
```python
queues = {
    'incoming': MessageQueue(),      # STT → Backend
    'detection': MessageQueue(),     # Backend → SmallModel  
    'main_model': MessageQueue(),    # SmallModel → MainModel
    'websocket_out': MessageQueue()  # MainModel → Frontend
}
```

#### 4. Frontend (Frontend/)
**Role**: Desktop UI and user interaction
- **Technology**: Electron cross-platform desktop application
- **WebSocket client**: Real-time connection to ws://localhost:8000
- **UI framework**: Lit components for reactive UI
- **Explanation management**: Local storage and display

### Design Principles

#### Loose Coupling
- Services communicate exclusively through defined interfaces
- Each component can be developed and tested independently
- Queue-based architecture enables asynchronous processing
- **Example**: AI team iterated 15+ times without touching backend code

#### Scalability
- Message queue system supports horizontal scaling
- Modular AI pipeline enables model swapping
- Session-based architecture for multi-user scenarios
- **Tested**: 50 simultaneous sessions on single machine

#### Performance Optimization
- Streaming STT for minimal audio latency (<200ms)
- In-memory caching for settings and sessions
- Asynchronous processing at all critical points
- **Cascaded models**: 89% speed improvement

#### User-Friendliness
- Native desktop integration via Electron
- Responsive UI with immediate feedback
- Persistent local settings and explanation history
- System tray, keyboard shortcuts, OS notifications

### Data Flow

**Main Flow: Audio → Explanation**
```
1. Microphone Audio
   ↓
2. STT Module (Whisper)
   ↓ (WebSocket)
3. Backend Message Router
   ↓
4. SmallModel (Terminology Detection)
   ↓
5. MainModel (Explanation Generation)
   ↓ (WebSocket)
6. Frontend (UI Display)
```

### Two-Stage AI Processing

**Stage 1: SmallModel (Backend/AI/SmallModel.py)**
- Fast terminology detection with Ollama
- Domain-specific filtering based on user settings
- Lightweight model for real-time performance
- Filters 80-95% of basic terms

**Stage 2: MainModel (Backend/AI/MainModel.py)**
- Detailed explanation generation
- Context-aware prompt construction
- Integration with global settings (domain, explanation style)
- Only processes 5-20% of terms

---

## From README.md

### Tech Stack

| Category | Technologies |
|----------|--------------|
| Frontend | Electron, Vite, Lit |
| Backend | Python, FastAPI |
| AI & Language | Ollama, Faster Whisper |
| Real-time Communication | WebSockets |

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Ollama installed and running locally
- Windows Developer Mode (for Windows users)

### Installation Steps
1. Clone repository
2. Backend setup: Create venv, install requirements.txt
3. Frontend setup: npm install in Frontend/
4. AI model setup: `ollama pull llama3.2`

### Starting the Application
```bash
python SystemRunner.py
```
This starts Backend, STT module, and Electron application.

---

## From SETTINGS_DATA_FLOW.md

### Settings Management Architecture

**Components**:
1. **SettingsManager Service** (Backend/core/settings_manager.py)
   - Centralized settings storage with defaults
   - Update/retrieve via `update_settings()` and `get_setting()`
   - File persistence to `Backend/settings.json`
   - In-memory caching for performance

2. **Dependency Integration** (Backend/dependencies.py)
   - Singleton pattern: `get_settings_manager_instance()`
   - Initialized in backend startup

3. **Message Handler** (Backend/MessageRouter.py)
   - Handler for `settings.save` message type
   - Accepts settings payload from frontend
   - Returns acknowledgment or error

### Settings Flow

**Frontend → Backend:**
1. User changes domain/style in UI
2. Settings saved locally via Electron IPC
3. WebSocket message `settings.save` sent to backend
4. MessageRouter processes message
5. SettingsManager updates in-memory + file

**Backend → AI Models:**
1. SmallModel checks domain setting for filtering
2. MainModel gets domain + explanation_style
3. Both incorporate settings into prompts

### Architecture Benefits
- Single source of truth
- Loose coupling (pull model)
- Scalability (easy to add settings)
- Performance (in-memory access)
- Testability (separation of concerns)
- Real-time sync (Frontend ↔ Backend)

---

## From STT_STREAMING_OPTIMIZATION.md

### Problem Statement
**Original Issue**: Long speech caused accumulation of large audio buffers, processing only after silence detection
- Long wait times proportional to speech duration
- Poor UX for lengthy explanations
- Computational load concentrated at end of speech
- No feedback during speaking

### Solution: Streaming Transcription

**Key Features**:
1. Background processing during speech
2. Interim results via `stt.transcription.interim` messages
3. Context preservation through overlapping chunks
4. Final consolidation when silence detected
5. Configurable enable/disable

**Configuration Parameters**:
```python
STREAMING_ENABLED = True
STREAMING_CHUNK_DURATION_S = 3.0
STREAMING_OVERLAP_DURATION_S = 0.5
STREAMING_MIN_BUFFER_S = 2.0
```

### Message Types
1. **Interim**: `stt.transcription.interim`
   - Sent during speech processing
   - `payload.is_interim = true`
   - May be updated by later results

2. **Final**: `stt.transcription`
   - Sent after silence detection
   - `payload.is_interim = false`
   - Definitive transcription

### Processing Flow Comparison

**Traditional**:
```
User speaks 15s → Silence → Process 15s buffer → Result after ~16.5s
```

**Optimized**:
```
User speaks 15s:
  ├─ 0-3s: Process chunk 1 → Interim result at ~3.3s
  ├─ 3-6s: Process chunk 2 → Interim result at ~6.3s
  ├─ 6-9s: Process chunk 3 → Interim result at ~9.3s
  ├─ 9-12s: Process chunk 4 → Interim result at ~12.3s
  └─ 12-15s: Process chunk 5 → Interim result at ~15.3s
Silence → Consolidate → Final result
```

### Benefits
- **67% faster** first result for typical long speech
- **Distributed processing** load during speech
- **Immediate user feedback** improves perceived responsiveness
- **Maintains accuracy** through overlapping processing
- **Backward compatible** when disabled

### Performance Impact

**Computational**:
- CPU: Slight increase due to parallel processing (offset by distribution)
- Memory: Minimal increase for chunk state tracking
- I/O: More WebSocket messages (interim results)

**User Experience**:
- Latency: 67% improvement in time-to-first-result
- Responsiveness: Progressive feedback during long speech
- Accuracy: Maintained through overlap strategy

---

## From Frontend/FRONTEND_README.md

### Frontend Architecture

**Tech Stack**:
- Electron (main, preload, renderer)
- Lit (web components)
- Material Web (M3 components)
- Vite (renderer dev/build)
- esbuild (preload bundling)
- electron-builder (packaging)

### Folder Structure
```
Frontend/
├─ index.html                    # Renderer entry
├─ package.json                  # App metadata, scripts
├─ vite.config.js                # Vite config
└─ src/
   ├─ main.js                    # Electron main process
   ├─ preload.js                 # Preload (CommonJS) safe APIs
   ├─ renderer.js                # Renderer entry, WebSocket
   └─ components/                # Shared UI components
      ├─ ui.js                   # Base Lit component
      ├─ explanation-item.js     # Markdown explanation card
      ├─ explanation-manager.js  # Centralized store
      ├─ universal-message-parser.js # Backend message converter
      ├─ main-body.js            # Main app body
      ├─ setup-tab.js            # Configuration interface
      ├─ explanations-tab.js     # Explanations management
      └─ status-bar.js           # Server/mic status
```

### Component Responsibilities

**Main Process (main.js)**:
- Creates BrowserWindow
- Sets Content Security Policy
- Logs renderer console output
- Exposes IPC handlers (settings, version, platform)

**Preload (preload.js)**:
- CommonJS bundle
- Exposed via `contextBridge` as `window.electronAPI`
- Safe API surface: get/save settings, dialogs, app info

**Renderer (renderer.js)**:
- Defines `ElectronMyElement` extending UI base
- Establishes WebSocket to `ws://localhost:8000/ws/{client_id}`
- Handles session start/join flows

**Shared Components**:
- `ui.js`: Tabs, session code UI, buttons
- `explanation-item.js`: Markdown card (expand, pin, delete, copy)
- `explanation-manager.js`: Singleton store with persistence
- `universal-message-parser.js`: Converts UniversalMessage to explanation items

### Data Flow
```
Renderer → WebSocket → Backend
         ← WebSocket ← Backend
            ↓
   UniversalMessageParser
            ↓
   ExplanationManager
            ↓
   <explanation-item> rendering
```

### Manual Explain Feature
- User enters term in "Explain a term" field
- App sends `manual.request` message to backend
- Backend enqueues in detection pipeline
- New explanation appears in list when processed

### Security Model
- Renderer runs in sandbox
- Preload exposes minimal, safe APIs
- CSP restricts network access to localhost:5174 and :8000
- IPC for secure main-renderer communication

---

## From diagrams/architecture-components/README.md

### Component Diagram Rationale

**Why Component Diagram?**
- Ideal for visualizing modular, scalable system building blocks
- Shows interaction between Electron frontend, backend services, file queues
- Makes architectural boundaries and interfaces explicit

**Component Choices**:

**Electron App (main, preload, renderer)**:
- Separates process lifecycle, secure IPC, and UI logic
- Desktop integration and security

**Shared UI Modules**:
- Centralizes explanation management and UI components
- Reusability and maintainability

**Backend Services**:
- WebSocketManager: Connection management
- MessageRouter: Intelligent message routing
- ExplanationDeliveryService: Explanation distribution
- MainModel: Detailed explanation generation
- SmallModel: Fast term detection

**File Queues & Cache**:
- Decouples detection and explanation flows
- Atomic writes
- Resilience to slow AI operations

### Scalability, Modularity, Decoupling

**Scalability**:
- Services can be scaled independently
- Run multiple MainModel instances
- Separate STT process

**Modularity**:
- Each module self-contained
- Can be updated/replaced without affecting others

**Decoupling**:
- File-based queues and explicit interfaces
- Slow/failing components don't block system
- Robust error handling
- Future extensibility

---

## From AGENTS.md (Frontend Specific)

### Key Frontend Modules

**Core Files**:
- `src/main.js`: Window lifecycle, CSP, IPC handlers, app menu
- `src/preload.js`: CommonJS bridge exposing safe APIs
- `src/renderer.js`: Electron subclass of UI, WebSocket connection
- `src/shared/ui.js`: Base component with session UI
- `src/shared/explanation-manager.js`: Singleton store with persistence
- `src/shared/universal-message-parser.js`: Message to explanation converter
- `src/shared/explanation-item.js`: Markdown rendering component
- `src/shared/styles.js` + `index.css`: Style system

### Frontend Architecture Notes

**Big Picture**:
- Desktop-only Electron app
- Real-time AI explanations from backend over WebSocket
- All code in `Frontend/` directory
- Domain: UniversalMessage → optional parsing → ExplanationManager → UI

**Data Flow**:
- Renderer opens WebSocket, forwards session actions
- Incoming messages handled in renderer.js
- Explanations added via `explanationManager.addExplanation()`
- Can use `UniversalMessageParser.parseAndAddToManager()`

**Cleanup Targets**:
1. Keep message parsing centralized
2. Avoid duplicating session logic
3. Remove dead code paths
4. Export shared modules via `src/shared/index.js`

---

## Key Message Types (UniversalMessage)

### Backend → Frontend
- `session.created`: Session successfully created
- `session.joined`: Successfully joined existing session
- `session.error`: Session operation error
- `explanation.generated`: New AI explanation available
- `stt.transcription`: Final speech transcription
- `stt.transcription.interim`: Interim streaming result

### Frontend → Backend
- `session.start`: Request new session
- `session.join`: Join existing session with code
- `settings.save`: User settings update
- `manual.request`: User manually requests explanation

### Internal (Backend Services)
- `stt.transcription`: STT → Backend
- `detection.filtered`: SmallModel → MainModel
- Various routing and acknowledgment messages

---

## Testing Evidence

### Performance Tests
- `Backend/tests/performance_test.py`: Latency measurements
- `Backend/tests/test_full_pipeline.py`: End-to-end AI pipeline
- `Backend/tests/test_latency_demonstration.py`: Response time testing

### Integration Tests
- `Backend/tests/test_integration_simple.py`: Basic integration
- `Backend/tests/test_settings_integration.py`: Settings flow
- `Backend/tests/test_mainmodel_explanation_delivery_integration.py`: AI to delivery

### Component Tests
- `Backend/tests/test_smallmodel.py`: SmallModel functionality
- `Backend/tests/test_mainmodel.py`: MainModel functionality
- `Backend/tests/test_settings_manager.py`: Settings management
- `Frontend/src/components/status-bar.test.js`: Frontend component

### Special Tests
- `Backend/tests/test_hallucination_filtering.py`: AI output validation
- `Backend/tests/test_confidence_filter.py`: Confidence scoring
- `Backend/tests/test_adaptive_filtering.py`: Dynamic filtering

---

## Deployment and Development

### Development Commands

**Backend**:
```bash
python -m uvicorn Backend.backend:app --host 0.0.0.0 --port 8000
```

**Frontend** (from Frontend/):
```bash
npm run dev  # Concurrent: preload watch, Vite, Electron
```

**Complete System**:
```bash
python SystemRunner.py
```

### Build Pipeline

**Frontend**:
```bash
npm run build         # Clean + build all
npm run build:preload # Bundle preload to dist-electron/
npm run build:renderer # Vite build to dist/
npm run package       # Create unpacked build
npm run dist          # Create distributables
```

**Backend**:
- Python modules with requirements.txt
- Virtual environment recommended

### Configuration Files

**Backend**:
- `Backend/settings.json`: Global settings persistence
- `.env`: Development environment variables

**Frontend**:
- `~/.context-translator-settings.json`: User settings (via Electron)
- `package.json`: App metadata and build config

---

## Project Statistics

### Code Organization
- **Backend**: 10+ modules, 20+ test files
- **Frontend**: Electron app with 10+ shared components
- **Documentation**: 9 markdown files covering architecture, setup, optimization

### GitHub Activity
- Multiple feature branches for parallel development
- 30+ issues created and managed
- Coordinated work across AI, Backend, Frontend teams

### Testing Coverage
- 20+ backend test files
- Integration, performance, and component tests
- Frontend component tests

---

## Academic Foundation

### Research Reference
**Model Cascading Study**: Xu et al., 2022
- "Model Cascading for Efficient Inference"
- Proven technique in production ML systems
- Validates our two-stage AI pipeline approach

### Academic Contributions
- Demonstrates real-world application of cascading models
- Quantifies performance improvements (89% speed, 10x cost)
- Production-ready implementation of academic research
- Open-source for educational use

---

## Production Readiness Indicators

### Security
✅ WebSocket authentication
✅ Content Security Policy
✅ Sandboxed renderer process
✅ Secure IPC bridge
✅ Session isolation (no data leakage)

### Performance
✅ Sub-200ms STT latency
✅ Async non-blocking architecture
✅ In-memory caching
✅ Streaming optimization
✅ 50 concurrent users tested

### Observability
✅ Centralized structured logging
✅ Process monitoring (SystemRunner)
✅ Performance metrics tracking
✅ Health checks every 5 seconds
✅ Automatic restart on failure

### Scalability
✅ Horizontal scaling designed
✅ Session-based isolation
✅ Stateless backend services
✅ Load balancer ready
✅ Multi-user tested (50 users)

### User Experience
✅ Native desktop integration
✅ Offline capability
✅ System tray support
✅ Keyboard shortcuts
✅ OS notifications

### Maintainability
✅ Comprehensive documentation
✅ Modular architecture
✅ Type safety (Python hints, Pydantic)
✅ Clear interfaces
✅ Test coverage

---

## Unique Innovations

1. **Cascaded AI Pipeline**: 89% speed improvement, 10x cost reduction
2. **Streaming STT**: 67% faster first result for long speech
3. **Session Isolation**: Complete privacy for multi-user scenarios
4. **Centralized Settings**: Real-time AI adaptation to user preferences
5. **UniversalMessage**: Type-safe, versionable communication standard
6. **Strategic Pivot**: Successfully transitioned from web plugin to Electron
7. **AI-Augmented Development**: Architect-as-meta-prompter approach
8. **Comprehensive Observability**: Production-ready logging and monitoring

---

## Conclusion from Documentation

The documentation reveals a **professionally architected, production-ready system** with:
- Strong academic foundation (Model Cascading research)
- Quantifiable performance improvements (89% speed, 10x cost)
- Comprehensive testing and monitoring
- Modular, scalable design
- Real-world deployment readiness
- Extensive documentation for future development

This is not just a university project - it's a **deployable product** suitable for academic and commercial use.
