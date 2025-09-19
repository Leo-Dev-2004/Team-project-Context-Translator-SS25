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

# Importiere WebSocketManager
from .services.WebSocketManager import WebSocketManager

# Importiere ExplanationDeliveryService
from .services.ExplanationDeliveryService import ExplanationDeliveryService

# Importiere die Funktionen zum Setzen und Holen von Instanzen aus dependencies.py
from .dependencies import (
    set_websocket_manager_instance,
    get_websocket_manager_instance,
)

# --- ANWENDUNGSWEITE LOGGING-KONFIGURATION ---
logging.basicConfig(
    level=logging.INFO, # Für Entwicklung bei DEBUG lassen, für Produktion auf INFO setzen
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
websocket_manager_instance: Optional[WebSocketManager] = None
message_router_instance: Optional[MessageRouter] = None
explanation_delivery_service_instance: Optional[ExplanationDeliveryService] = None


# --- FASTAPI-ANWENDUNGS-STARTUP-EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")
    global simulation_manager_instance, websocket_manager_instance, message_router_instance
    global queue_status_sender_task, explanation_delivery_service_instance

    # Step 1: Initialize all standalone services FIRST.
    # These services do not depend on others during their __init__.
    websocket_manager_instance = WebSocketManager(
        incoming_queue=queues.incoming,
        outgoing_queue=queues.websocket_out,
    )
    set_websocket_manager_instance(websocket_manager_instance)
    session_manager_instance = SessionManager()
    set_session_manager_instance(session_manager_instance)
    logger.info("SessionManager and WebSocketManager initialized and set.")

    # Step 2: NOW initialize the MessageRouter, which depends on the services above.
    # Its __init__ can now safely call get_session_manager_instance().
    message_router_instance = MessageRouter()
    logger.info("MessageRouter initialized with dependencies.")

    # Step 3: Initialize ExplanationDeliveryService
    explanation_delivery_service_instance = ExplanationDeliveryService(
        outgoing_queue=queues.websocket_out
    )
    logger.info("ExplanationDeliveryService initialized.")

    # Step 4: Start all background tasks.
    await websocket_manager_instance.start()
    await message_router_instance.start()
    await explanation_delivery_service_instance.start()
    queue_status_sender_task = asyncio.create_task(send_queue_status_to_frontend())

    logger.info("Application startup complete. All services started.")



async def send_queue_status_to_frontend():
    while True:
        await asyncio.sleep(1)
        try:
            websocket_manager = get_websocket_manager_instance()
            if not websocket_manager or not websocket_manager.connections:
                continue

            status_payload = {
                "from_frontend_q_size": queues.incoming.qsize(),
                "to_frontend_q_size": queues.websocket_out.qsize()
            }

            # Iterate over a copy of the client IDs
            for client_id in list(websocket_manager.connections.keys()):
                # Only send to clients that are identified as frontends
                if client_id.startswith("frontend_renderer_"):
                    status_message = UniversalMessage(
                        type="system.queue_status_update",
                        payload=status_payload,
                        destination=client_id,  # Use the specific client_id
                        origin="backend.monitor",
                        client_id=client_id
                    )
                    await queues.websocket_out.enqueue(status_message)

        except Exception as e:
            logger.error(f"Error in status sending task: {e}", exc_info=True)


# --- FASTAPI-ANWENDUNGS-SHUTDOWN-EVENT (KORRIGIERT) ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    # Zugriff auf die relevanten globalen Instanzen
    global simulation_manager_instance, websocket_manager_instance
    global queue_status_sender_task, message_router_instance, explanation_delivery_service_instance

    # 1. Hintergrund-Tasks abbrechen (z.B. der Queue-Status-Sender)
    if queue_status_sender_task and not queue_status_sender_task.done():
        logger.info("Cancelling queue_status_sender_task...")
        queue_status_sender_task.cancel()
        try:
            await queue_status_sender_task
        except asyncio.CancelledError:
            logger.info("queue_status_sender_task cancelled gracefully.")

    if message_router_instance:
        logger.info("Stopping MessageRouter...")
        try:
            await message_router_instance.stop()
        except Exception as e:
            logger.error(f"Error during MessageRouter shutdown: {e}", exc_info=True)

    if explanation_delivery_service_instance:
        logger.info("Stopping ExplanationDeliveryService...")
        try:
            await explanation_delivery_service_instance.stop()
        except Exception as e:
            logger.error(f"Error during ExplanationDeliveryService shutdown: {e}", exc_info=True)

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