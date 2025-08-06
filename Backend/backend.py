# Backend/backend.py
import asyncio
import logging
import uuid
import time
from typing import Optional, cast 
from starlette.websockets import WebSocketDisconnect, WebSocketState 
from .dependencies import set_session_manager_instance
from .core.session_manager import SessionManager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .AI.SmallModel import SmallModel

# Import all message-related models from message_types.py
# Annahme: UniversalMessage, DeadLetterMessage, ProcessingPathEntry,
# ForwardingPathEntry und ErrorTypes sind alle in dieser einen Datei definiert.
from .models.UniversalMessage import ( 
    UniversalMessage,
    ProcessingPathEntry,
    ForwardingPathEntry,
    ErrorTypes,
)

# Import the API router 
from .api import endpoints # <--- ADDED THIS EXPLICIT IMPORT FOR ENDPOINTS

# Korrigierter Import für den abstrakten Queue-Typ (relativer Pfad und Kleinbuchstaben im Dateinamen)
from .queues.QueueTypes import AbstractMessageQueue

from .core.Queues import queues # Zugriff auf die vorinitialisierten Queues
from .queues.MessageQueue import MessageQueue # Für Type Hinting (ebenfalls relativ, falls im selben Verzeichnis)
from .MessageRouter import MessageRouter # Importiere die MessageRouter-Klasse (Annahme: sie ist in Backend/)

# Importiere die SimulationManager-Klasse (für Type Hinting und Instanziierung)
# WICHTIG: Dateiname ist 'SimulationManager.py' (Großbuchstaben), daher hier auch Großbuchstaben
from .core.simulator import SimulationManager 

# Importiere WebSocketManager
from .services.WebSocketManager import WebSocketManager

# Importiere die Funktionen zum Setzen und Holen von Instanzen aus dependencies.py
from .dependencies import (
    set_simulation_manager_instance, 
    get_simulation_manager, 
    set_websocket_manager_instance, 
    get_websocket_manager_instance,
)

# --- ANWENDUNGSWEITE LOGGING-KONFIGURATION ---
logging.basicConfig(
    level=logging.DEBUG, # Für Entwicklung bei DEBUG lassen, für Produktion auf INFO setzen
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)
logger = logging.getLogger(__name__)

# --- FASTAPI-ANWENDUNGSINSTANZ ---
app = FastAPI()

# --- FASTAPI-MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost",    # Hinzugefügt für breitere localhost-Kompatibilität
        "http://127.0.0.1",    # Hinzugefügt für breitere localhost-Kompatibilität
        "null",                # Hinzugefügt für file:// oder bestimmte Client-Typen
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# --- API-ROUTER EINBEZIEHEN ---
app.include_router(endpoints.router)

# --- GLOBALE INSTANZEN für Hintergrundaufgaben ---
# Diese werden während des Startup-Events gesetzt
queue_status_sender_task: Optional[asyncio.Task] = None
simulation_manager_instance: Optional[SimulationManager] = None
websocket_manager_instance: Optional[WebSocketManager] = None
message_router_instance: Optional[MessageRouter] = None 


# --- FASTAPI-ANWENDUNGS-STARTUP-EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")
    # ... (global-Deklarationen anpassen)

    # 1. WebSocketManager bleibt wie er ist.
    websocket_manager_instance = WebSocketManager(
        incoming_queue=queues.incoming,
        outgoing_queue=queues.websocket_out,
    )
    set_websocket_manager_instance(websocket_manager_instance)
    await websocket_manager_instance.start()
    logger.info("WebSocketManager initialisiert und gestartet.")

    # 2. MessageRouter ist jetzt der zentrale Prozessor.
    message_router_instance = MessageRouter() # Er holt sich die Queues selbst.
    await message_router_instance.start()
    logger.info("MessageRouter initialisiert und gestartet.")

    # 3. BackendServiceDispatcher wird NICHT MEHR initialisiert. <-- ENTFERNEN

    # 4. SimulationManager bleibt wie er ist.
    simulation_manager_instance = SimulationManager()
    set_simulation_manager_instance(simulation_manager_instance)
    logger.info("SimulationManager initialisiert und gesetzt.")

    # 5. SmallModel-Instanziierung hier entfernen. <-- ENTFERNEN

    # 6. Queue-Status-Sender bleibt.
    queue_status_sender_task = asyncio.create_task(send_queue_status_to_frontend())
    logger.info("Queue status sender task gestartet.")

    logger.info("Anwendungsstart abgeschlossen.")


async def send_queue_status_to_frontend():
    logger.info("send_queue_status_to_frontend task started.")
    while True:
        await asyncio.sleep(1) # Sleep at the beginning of the loop
        try:
            websocket_manager = get_websocket_manager_instance()
            if not websocket_manager or not websocket_manager.connections:
                continue

            status_payload = {
                "from_frontend_q_size": queues.incoming.qsize(),
                "to_frontend_q_size": queues.websocket_out.qsize()
            }

            # Create a copy of connection keys to iterate safely
            all_client_ids = list(websocket_manager.connections.keys())

            for client_id in all_client_ids:
                # HIER IST DIE NEUE LOGIK:
                # Send status updates only to clients identified as frontends.
                if client_id.startswith("frontend_renderer_"):
                    status_message = UniversalMessage(
                        type="system.queue_status_update",
                        payload=status_payload,
                        destination=client_id, # Send to the specific client
                        origin="backend.monitor",
                        client_id=client_id,
                    )
                    # Use the websocket_out_queue to send the message
                    await queues.websocket_out.enqueue(status_message)
                    logger.debug(f"Enqueued queue status for frontend client {client_id}")

        except Exception as e:
            logger.error(f"Error in send_queue_status_to_frontend task: {e}", exc_info=True)


# --- FASTAPI-ANWENDUNGS-SHUTDOWN-EVENT (KORRIGIERT) ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    # Zugriff auf die relevanten globalen Instanzen
    global simulation_manager_instance, websocket_manager_instance
    global queue_status_sender_task, message_router_instance

    # 1. Hintergrund-Tasks abbrechen (z.B. der Queue-Status-Sender)
    if queue_status_sender_task and not queue_status_sender_task.done():
        logger.info("Cancelling queue_status_sender_task...")
        queue_status_sender_task.cancel()
        try:
            await queue_status_sender_task
        except asyncio.CancelledError:
            logger.info("queue_status_sender_task cancelled gracefully.")

    # 2. Logik-Module stoppen (SimulationManager, MessageRouter)
    # Diese Dienste könnten noch versuchen, Nachrichten zu senden.
    if simulation_manager_instance:
        logger.info("Stopping SimulationManager...")
        try:
            await simulation_manager_instance.stop()
        except Exception as e:
            logger.error(f"Error during SimulationManager shutdown: {e}", exc_info=True)

    if message_router_instance:
        logger.info("Stopping MessageRouter...")
        try:
            await message_router_instance.stop()
        except Exception as e:
            logger.error(f"Error during MessageRouter shutdown: {e}", exc_info=True)

    # 3. WebSocketManager als LETZTES stoppen
    # Dies stellt sicher, dass alle vorherigen Dienste die Möglichkeit hatten,
    # letzte Nachrichten an die Clients zu senden.
    if websocket_manager_instance:
        logger.info("Shutting down WebSocketManager (closing all client connections)...")
        try:
            await websocket_manager_instance.stop()
            logger.info("WebSocketManager shutdown complete.")
        except Exception as e:
            logger.error(f"Error during WebSocketManager shutdown: {e}", exc_info=True)

    logger.info("Application shutdown complete.")


# --- WebSocket-Endpunkt (KORRIGIERT) ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    logger.info(f"Incoming WebSocket connection for client_id: {client_id}")

    ws_manager = get_websocket_manager_instance()
    if ws_manager:
        try:
            # Die gesamte Verbindungs-Logik wird an den Manager übergeben
            await ws_manager.handle_connection(websocket, client_id)
        except WebSocketDisconnect:
            # Dieser Log ist nützlich, um Disconnects auf der Endpoint-Ebene zu sehen
            logger.info(f"WebSocket disconnected for client_id: {client_id} (handled by manager).")
        except Exception as e:
            logger.error(f"Unhandled error in WebSocket endpoint for {client_id}: {e}", exc_info=True)
    else:
        # Fallback, falls der Manager beim Start nicht initialisiert werden konnte
        logger.error("WebSocketManager not initialized. Closing connection.")
        await websocket.close(code=1011, reason="Server internal error: WebSocketManager not ready.")

# --- Hauptausführungsblock (für direkte Skriptausführung mit Uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    session_manager_instance = SessionManager()
    set_session_manager_instance(session_manager_instance)      
    logger.info("SessionManager initialisiert und gesetzt.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
