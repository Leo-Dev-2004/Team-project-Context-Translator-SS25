# Deep Analysis: Real-time AI Contextual Assistant

## 1\. Executive Summary

This project is a multi-process, service-oriented **desktop application** providing real-time contextual assistance. It comprises four main, independently running components: a **System Runner** for orchestration, an **STT Service** for voice transcription, a **FastAPI Backend** for AI processing and communication, and an **Electron Frontend** for user interaction.

The core workflow is as follows:

1  The **STT Service** captures microphone audio, transcribes it using Voice Activity Detection (VAD) and `faster-whisper`, and sends the text to the Backend.
2. The **Backend** receives the text and initiates a two-stage AI pipeline:
      *`SmallModel` detects technical terms and writes them to a `detections_queue.json` file.
      *`MainModel` reads from this queue, generates explanations for the terms using a local LLM, and writes them to an `explanations_queue.json` file.
3. An `ExplanationDeliveryService` polls the explanations queue and pushes completed explanations to the **Electron Frontend** via a WebSocket.
4. The **Frontend** receives the explanation and displays it to the user in a managed list.

The architecture emphasizes **decoupling and asynchronicity**, using WebSockets for real-time client-server communication and file-based queues to buffer and manage the AI workload, preventing data loss and ensuring system stability.

-----

## 2\. System-Wide Concepts & Data Formats

### 2.1. The `UniversalMessage` Data Format

This `pydantic` model is the **standardized data structure** for all communication, both within the backend and over WebSockets.

  ***Structure:**

    ```python
    class UniversalMessage(BaseModel):
        id: str            # Unique message UUID
        type: str          # Defines the message's purpose (e.g., "command.start_session")
        payload: Dict      # The actual data, content varies with 'type'
        timestamp: float   # Unix timestamp of creation
        origin: str        # Component that created the message (e.g., "frontend", "STTService")
        destination: str   # Intended recipient (e.g., a specific client_id, "all_frontends")
        client_id: str     # WebSocket client ID of the sender, if applicable
        # Path tracking for debugging
        processing_path: List[ProcessingPathEntry]
        forwarding_path: List[ForwardingPathEntry]
    ```
  ***Example `type` values:**
      * `stt.transcription`: Contains transcribed text from the STT service.
      * `session.start` / `session.join`: Commands from the frontend to manage sessions.
      * `manual.request`: A user-initiated request to explain a specific term.
      * `explanation.generated`: Contains a complete explanation object for the frontend.
      * `session.created` / `session.joined`: Backend responses confirming session status.
      * `error.*`: Standardized error messages.

### 2.2. Asynchronous Communication & Decoupling

  ***WebSockets:** The primary method for real-time, bidirectional communication between the backend and individual clients (both the Frontend and the STT service). Managed by `WebSocketManager.py`.
  ***File-Based Queues:** The core of the decoupled AI pipeline. They allow the term detection service (`SmallModel`) and the explanation generation service (`MainModel`) to operate independently without direct interaction. This design is resilient to failures or slowdowns in the AI models.
      *`Backend/AI/detections_queue.json`: A JSON array of "detection" objects. `SmallModel` is the **producer**, writing new terms here. `MainModel` is the **consumer**.
      * `Backend/AI/explanations_queue.json`: A JSON array of "explanation" objects. `MainModel` is the **producer**. `ExplanationDeliveryService` is the **consumer**.
      * **Atomic Writes:** To prevent race conditions and data corruption, all writes to these files use a safe, atomic operation: write to a temporary file (`*.tmp`) and then perform an OS-level rename, which is an atomic action. This is implemented in both `MainModel` and `SmallModel`.

-----

## 3\. Component Deep Dive

### 3.1. System Runner (`SystemRunner.py`)

  ***Role:** The master script and **entry point** for the entire application. It orchestrates the startup and shutdown of all other services.
  ***Key Logic & Features:**
      ***Session ID Generation:** Creates a single, unique `user_session_id` (`user_{uuid}`) at startup.
      ***Process Launching:** Uses Python's `subprocess.Popen` to launch the other three main processes:
        1.  The FastAPI Backend (`uvicorn`).
        2.  The STT Service (`transcribe.py`), passing the `user_session_id` as a command-line argument.
        3.  The Electron Frontend (`npm run dev:main`), also passing the `user_session_id`.
      ***Log Aggregation:** Captures the `stdout` and `stderr` of each child process and forwards them to its own console with a prefix (e.g., `[BACKEND]`, `[STT]`) for centralized monitoring.
      * **Health Check:** Waits for the backend to become available by polling its `/health` endpoint before starting the other services.
      * **Graceful Shutdown:** Implements a `shutdown` function that uses `psutil` to find and terminate the entire process tree for each service, ensuring no orphaned processes are left running.
      * **File Flushing:** On startup, it clears the contents of the JSON queue files (`detections_queue.json`, `explanations_queue.json`) to ensure a clean state for each run.

### 3.2. Speech-to-Text (STT) Service (`Backend/STT/transcribe.py`)

  ***Role:** A dedicated, standalone process for high-performance, real-time audio transcription.
  ***Key Logic & Features:**
      ***VAD (Voice Activity Detection):** This is the core feature for responsiveness. Instead of transcribing continuously, it:
        1.  Listens to the audio stream from the microphone (`sounddevice`).
        2.  Calculates the energy of each audio chunk.
        3.  Buffers audio chunks only when the energy is above a `VAD_ENERGY_THRESHOLD`.
        4.  Detects the end of a sentence or phrase when a period of silence (`VAD_SILENCE_DURATION_S`) is observed.
        5.  This "record-then-transcribe" approach sends complete sentences to the `faster-whisper` model, yielding more accurate and coherent results than word-by-word transcription.
      * **Transcription:** Uses the `faster-whisper` library, a highly optimized implementation of OpenAI's Whisper model, for fast and accurate transcription.
      * **Client Communication:** Connects to the backend as a dedicated WebSocket client. After transcribing a sentence, it packages the text into a `UniversalMessage` with `type: 'stt.transcription'` and sends it to the backend.

### 3.3. Backend Service (FastAPI)

#### 3.3.1. Core Application & Lifecycle (`Backend/backend.py`)

  ***Role:** Sets up the FastAPI application, manages global state, and orchestrates the application's startup and shutdown events.
  ***Key Logic & Features:**
      ***Dependency Injection:** Initializes and provides singleton instances of key services (`WebSocketManager`, `MessageRouter`, `SessionManager`, `ExplanationDeliveryService`, `MainModel`) for use across the application.
      * **Startup (`@app.on_event("startup")`):**
        1.  Initializes the `MainModel` instance.
        2.  Creates and starts the main `asyncio.Task` for `MainModel.run_continuous_processing()`.
        3.  Starts the background tasks for all other key services (e.g., `MessageRouter.start()`).
      * **Shutdown (`@app.on_event("shutdown")`):**
        1.  Gracefully cancels all background tasks.
        2.  Calls the `stop()` method on services like `WebSocketManager` to close connections properly.
        3.  Calls `main_model.close()` to shut down its `httpx` client.

#### 3.3.2. AI Pipeline - Term Detector (`Backend/AI/SmallModel.py`)

  ***Role:** The **producer** of the AI pipeline. It processes raw text to find terms that need explaining.
  ***Input:** A `UniversalMessage` containing transcribed text.
  ***Key Logic & Features:**
      ***AI-Powered Detection:** Constructs a detailed prompt for a local LLM (e.g., `llama3.2`) asking it to identify technical terms in a sentence and return them as a JSON array with `term` and `confidence` fields.
      ***Robust JSON Parsing:** Includes a `safe_json_extract` method that uses regex and string searching to aggressively find and parse a valid JSON array from the LLM's potentially messy raw output.
      * **Filtering:** A `should_pass_filters` method prevents over-explaining common terms. It filters out terms with low confidence and implements a **cooldown period** for each term to avoid repeated explanations in a short time.
      ***Fallback Mechanism:** If the AI query fails, `detect_terms_fallback` uses a predefined dictionary of regex patterns to perform basic keyword matching as a backup.
  ***Output:** Writes a list of "detection" objects to `detections_queue.json`.
  ***Data Format (`detections_queue.json` entry):**
    ```json
    {
      "id": "det_...",
      "term": "neural network",
      "context": "The speaker is discussing a neural network.",
      "timestamp": 1678886400.0,
      "status": "pending", // or "processed"
      "user_role": "student",
      "confidence": 0.95,
      "client_id": "stt_client_..."
    }
    ```

#### 3.3.3. AI Pipeline - Explanation Generator (`Backend/AI/MainModel.py`)

  ***Role:** The **consumer** of `detections_queue.json` and the **producer** for `explanations_queue.json`. It generates the actual explanations.
  ***Input:** Reads "detection" objects with `status: "pending"` from `detections_queue.json`.
  ***Key Logic & Features:**
      ***Continuous Processing Loop:** The `run_continuous_processing` method runs in an `asyncio` loop, periodically calling `process_detections_queue`.
      ***Queue Processing:**
        1.  Safely reads the entire `detections_queue.json` file under a lock.
        2.  Identifies all pending items and **immediately updates their status to "processed" in-memory**.
        3.  Writes the updated list back to the file. This prevents other instances or runs from re-processing the same items.
        4.  Processes the identified items *outside* the file lock to avoid blocking.
      * **Caching:** Before querying the LLM, it checks for the term in a local file cache (`explanation_cache.json`). If a cached explanation exists, it is used directly.
      ***LLM Query:** If not cached, it builds a prompt for the LLM to explain the term, optionally considering the user's role for tailored explanations. It uses `httpx.AsyncClient` for non-blocking HTTP requests to the Ollama API.
  ***Output:** Writes an "explanation" object to `explanations_queue.json` and saves new explanations to the cache.
  ***Data Format (`explanations_queue.json` entry):**
    ```json
    {
      "id": "exp_...",
      "original_detection_id": "det_...",
      "term": "neural network",
      "explanation": "A neural network is a series of algorithms...",
      "timestamp": 1678886401.0,
      "status": "ready_for_delivery", // or "delivered"
      "client_id": "stt_client_...",
      "confidence": 0.95
    }
    ```

#### 3.3.4. Explanation Delivery Service (`Backend/services/ExplanationDeliveryService.py`)

  ***Role:** A service that bridges the gap between the static `explanations_queue.json` file and the live WebSocket clients.
  ***Input:** Polls `explanations_queue.json` periodically.
  ***Key Logic & Features:**
      ***Polling Loop:** Runs an async loop that reads `explanations_queue.json` under a lock.
      ***Status Filtering:** It looks for entries with `status: "ready_for_delivery"`.
      ***Message Formatting:** For each ready explanation, it creates a `UniversalMessage` with `type: 'explanation.generated'` and the explanation object as its payload.
      ***Queue Forwarding:** It `enqueue`s the `UniversalMessage` into the main `websocket_out_queue`, from which the `WebSocketManager` will broadcast it to the appropriate clients.
      * **Status Update:** After queueing the messages for delivery, it updates the status of the corresponding entries in `explanations_queue.json` to `"delivered"` in a single batch write to prevent re-delivery.

### 3.4. Frontend (Electron)

#### 3.4.1. Main Process (`Frontend/src/main.js`)

  ***Role:** The entry point for the Electron application. It manages the native window, application lifecycle, and secure communication with the renderer process.
  ***Key Logic & Features:**
      ***Window Creation:** Creates and configures the `BrowserWindow`, setting its size, title, and making it frameless on Windows to allow for a custom title bar.
      ***Content Security Policy (CSP):** Implements a strict CSP to enhance security. It only allows connections to the Vite dev server (`localhost:5174`) and the backend WebSocket/API (`localhost:8000`).
      ***IPC Handling (`ipcMain`):** Sets up handlers for requests from the renderer process. This includes getting the app version, platform details, and, crucially, retrieving the `user_session_id` that was passed to it as a command-line argument by the `SystemRunner`.
      * **Dev vs. Prod Loading:** In development, it loads the UI from the Vite dev server URL. In production, it loads the static `index.html` file from the build directory.

#### 3.4.2. Renderer Process (`Frontend/src/renderer.js`)

  ***Role:** The main logic of the UI, running within the browser window's context. It handles all communication with the backend and manages the user interface state.
  ***Key Logic & Features:**
      ***WebSocket Initialization:** On startup, it generates a unique `client_id` for itself and establishes a WebSocket connection to the backend.
      ***Handshake:** Upon connection, it calls `_performHandshake`, which uses the `window.electronAPI` (exposed by `preload.js`) to get the `user_session_id` from the main process and sends a `frontend.init` message to the backend.
      ***Message Processing Queue:** To avoid blocking the UI thread with a potential flood of messages, it does not process WebSocket messages immediately. Instead, it pushes incoming messages into a simple array (`this.messageQueue`) and processes them sequentially with a small delay in `_processMessageQueue`.
      ***Command Sending:** Provides methods like `_startSession`, `_joinSession`, and `_sendManualRequest` which create and send `UniversalMessage` objects to the backend in response to user actions (e.g., button clicks).
      ***Handling `explanation.generated`:** When a message of this type is received, it calls `_handleNewExplanation`, which adds the new explanation to the `explanationManager`.
      * **Notification System:** Implements a simple, non-blocking notification system (`_showNotification`) to give the user feedback on actions (e.g., "Session created," "Explanation requested").

#### 3.4.3. UI State & Components (`ui.js`, `explanation-manager.js`, `explanation-item.js`)

  ***`explanation-manager.js` (Singleton Store):**
      ***Role:** The single source of truth for all explanation data on the client side.
      ***Features:**
          ***State Management:** Holds an array of all explanation objects.
          ***Persistence:** Automatically saves the entire state to `sessionStorage` on any change (throttled to prevent excessive writes) and loads it on startup.
          ***Pinning & Sorting:** Allows explanations to be "pinned," which keeps them at the top of the list. The list is always sorted with pinned items first, then by creation time.
          ***Memory Management:** Limits the total number of unpinned explanations to prevent the app from consuming too much memory over a long session.
          ***Listener Pattern:** Notifies the UI (and any other listeners) whenever the data changes, triggering a re-render.
  ***`explanation-item.js` (Lit Component):**
      ***Role:** Renders a single explanation card.
      ***Features:** Displays the title, content, timestamp, and a confidence badge. Handles user interactions like pinning, deleting, copying content, and expanding/collapsing the explanation body. It uses the `marked` library to render the explanation content as Markdown.
  ***`ui.js` (Base Lit Component):**
      ***Role:** Provides the main application shell, including the tabbed interface ("Setup" and "Explanations"), session management controls, and the area for manual term requests. It renders the list of `explanation-item` components by mapping over the data from the `explanationManager`.

#### 3.4.4. Universal Message Parser (`universal-message-parser.js`)

  ***Role:** A stateless utility class designed to decouple the frontend's internal data model from the backend's `UniversalMessage` format.
  ***Key Logic & Features:**
      ***`parseToExplanationItem(message)`:** The main function. It takes a raw `UniversalMessage` and attempts to convert it into a standardized "Explanation Item" object suitable for the `explanationManager`.
      ***Heuristics:** It uses a series of heuristics to intelligently extract the title and content from the message's `payload`, as the relevant data might be in different fields (e.g., `payload.term`, `payload.explanation.content`, `payload.title`). This makes the frontend resilient to minor changes in the backend's payload structure.
      ***Validation:** Includes basic validation to ensure the incoming object looks like a `UniversalMessage` before attempting to parse it.