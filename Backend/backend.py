# Backend/backend.py
import asyncio
import logging
import uuid
import time
from typing import Optional, cast 
from starlette.websockets import WebSocketDisconnect, WebSocketState 

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

# Importiere BackendServiceDispatcher direkt
from .core.BackendServiceDispatcher import BackendServiceDispatcher

# Importiere WebSocketManager
from .services.WebSocketManager import WebSocketManager

# Importiere die Funktionen zum Setzen und Holen von Instanzen aus dependencies.py
from .dependencies import (
    set_simulation_manager_instance, 
    get_simulation_manager, 
    set_websocket_manager_instance, 
    get_websocket_manager_instance,

    # SICHERSTELLEN: Diese sind korrekt in Backend/dependencies.py definiert
    set_backend_service_dispatcher_instance, 
    get_backend_service_dispatcher_instance 
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

# --- ANWENDUNGSZUSTAND ---
# Dieses Set könnte redundant werden, wenn WebSocketManager ausschließlich Verbindungen verwaltet.
# Vorerst beibehalten, falls andere Teile deiner App sich noch darauf für direkten WebSocket-Zugriff verlassen.
app.state.websockets = set() 

# --- GLOBALE INSTANZEN für Hintergrundaufgaben ---
# Diese werden während des Startup-Events gesetzt
message_processor_task: Optional[asyncio.Task] = None
queue_status_sender_task: Optional[asyncio.Task] = None

backend_service_dispatcher_instance: Optional[BackendServiceDispatcher] = None 
simulation_manager_instance: Optional[SimulationManager] = None
websocket_manager_instance: Optional[WebSocketManager] = None
message_router_instance: Optional[MessageRouter] = None 


# --- FASTAPI-ANWENDUNGS-STARTUP-EVENT ---
@app.on_event("startup")
async def startup_event():
    #logger.info("Application startup event triggered.")
    global backend_service_dispatcher_instance, simulation_manager_instance, websocket_manager_instance
    global message_processor_task, queue_status_sender_task, message_router_instance

    # 1. WebSocketManager ZUERST initialisieren, da andere Dienste (wie der Dispatcher) davon abhängen könnten.
    # Er benötigt die websocket_out_queue, um Nachrichten an Clients zu senden.
    websocket_manager_instance = WebSocketManager(       
        incoming_queue=queues.incoming,          # Incoming messages from WS clients
        outgoing_queue=queues.websocket_out,# Messages specifically for WS clients
)
    set_websocket_manager_instance(websocket_manager_instance) # Über dependencies global zugänglich machen
    logger.info("WebSocketManager initialisiert und gesetzt.")

    await websocket_manager_instance.start()
    logger.info("WebSocketManager initializied and set.")

    # 2. BackendServiceDispatcher initialisieren
    backend_service_dispatcher_instance = BackendServiceDispatcher(
        incoming_queue=queues.incoming,
        outgoing_queue=queues.outgoing,
        websocket_out_queue=queues.websocket_out
        )
    # SICHERSTELLEN: set_backend_service_dispatcher_instance existiert in dependencies.py
    set_backend_service_dispatcher_instance(backend_service_dispatcher_instance) # Global setzen

    await backend_service_dispatcher_instance.initialize() # Asynchrone Einrichtung durchführen
    # Den Verarbeitungsprozess als Hintergrundaufgabe starten.
    message_processor_task = asyncio.create_task(backend_service_dispatcher_instance.start()) 
    logger.info("BackendServiceDispatcher initialisiert und gestartet.")

    # 3. SimulationManager initialisieren -- !!! ANGEPASST AN DEINE LETZTE SimulationManager.py SGINATUR !!!
    # Die Parameter hier MÜSSEN mit der __init__-Methode in Backend/core/SimulationManager.py übereinstimmen.
    simulation_manager_instance = SimulationManager(
        incoming_queue=queues.incoming,
        outgoing_queue=queues.outgoing,
        websocket_out_queue=queues.websocket_out    
        )
    set_simulation_manager_instance(simulation_manager_instance) # Global zugänglich machen
    logger.info("SimulationManager initialisiert und gesetzt.")

    # 4. MessageRouter initialisieren (falls hier explizit instanziiert werden muss)
    # Annahme: MessageRouter hat keine komplexen Init-Argumente oder holt seine Abhängigkeiten dynamisch.
    # Falls er `queues` oder `dispatcher_instance` etc. benötigt, müssen diese hier übergeben werden.
    message_router_instance = MessageRouter()
    await message_router_instance.start()
    logger.info("MessageRouter initializing and starting") 

    # Zwischenschritt SmallModel starten
    small_model_instance = SmallModel()

    # 5. Den Task zum Senden des Queue-Status starten
    queue_status_sender_task = asyncio.create_task(send_queue_status_to_frontend())
    logger.info("Queue status sender task gestartet.")

    logger.info("Anwendungsstart abgeschlossen. Alle Dienste initialisiert.")


async def send_queue_status_to_frontend():
    logger.info("send_queue_status_to_frontend: Funktion sofort betreten. (Test 2)")

    while True:
        try:
            incoming_q: AbstractMessageQueue = queues.incoming
            websocket_out_q: AbstractMessageQueue = queues.websocket_out

            incoming_q_size = incoming_q.qsize()
            websocket_out_q_size = websocket_out_q.qsize()

            status_message_data = {
                "from_frontend_q_size": incoming_q_size,      
                "to_frontend_q_size": websocket_out_q_size
            }
            # logger.info(f"Sending queue status update with payload: {status_message_data}")

            websocket_manager_instance_local: Optional[WebSocketManager] = get_websocket_manager_instance() 

            if websocket_manager_instance_local and websocket_manager_instance_local.connections: 
                for client_id_str in list(websocket_manager_instance_local.connections.keys()):
                    try:
                        queue_status_universal_message = UniversalMessage(
                            id=str(uuid.uuid4()),
                            type="system.queue_status_update",
                            origin="backend.system_monitor",
                            destination="frontend",
                            timestamp=time.time(),
                            client_id=client_id_str, 
                            payload=status_message_data,
                            processing_path=[], 
                        )

                        if hasattr(websocket_manager_instance_local, 'send_message_to_client'):
                            await websocket_manager_instance_local.send_message_to_client(client_id_str, queue_status_universal_message)
                            #logger.debug(f"Sent queue status (UniversalMessage) to client {client_id_str}")
                        elif websocket_manager_instance_local.connections.get(client_id_str):
                            await websocket_manager_instance_local.connections[client_id_str].send_text(
                                queue_status_universal_message.model_dump_json() 
                            )
                            #logger.debug(f"Sent queue status directly via WS (JSON) to {client_id_str}")
                        else:
                            logger.warning(f"No suitable method or active connection for {client_id_str} to send queue status.")

                    except Exception as client_send_error:
                        logger.error(f"Error sending queue_status_update to client {client_id_str}: {client_send_error}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in send_queue_status_to_frontend task: {e}", exc_info=True)
        await asyncio.sleep(1) 


# --- FASTAPI-ANWENDUNGS-SHUTDOWN-EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    # Zugriff auf globale Instanzen direkt
    global backend_service_dispatcher_instance, simulation_manager_instance, websocket_manager_instance
    global message_processor_task, queue_status_sender_task

    # 1. Den Queue-Status-Sender-Task zuerst abbrechen
    if queue_status_sender_task:
        logger.info("Cancelling queue_status_sender_task...")
        queue_status_sender_task.cancel()
        try:
            await asyncio.wait_for(queue_status_sender_task, timeout=1.0)
        except asyncio.CancelledError:
            logger.info("queue_status_sender_task cancelled gracefully.")
        except asyncio.TimeoutError:
            logger.warning("queue_status_sender_task did not stop cleanly within timeout.")
    else:
        logger.warning("queue_status_sender_task not found for graceful shutdown.")

    # 2. Die Simulation stoppen, falls sie läuft
    if simulation_manager_instance:
        try:
            if hasattr(simulation_manager_instance, 'is_running') and simulation_manager_instance.is_running:
                await simulation_manager_instance.stop()
                logger.info("SimulationManager explicitly stopped.")
            elif hasattr(simulation_manager_instance, 'stop'): 
                await simulation_manager_instance.stop()
                logger.info("SimulationManager stop method called.")
        except Exception as e:
            logger.error(f"Error during SimulationManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("SimulationManager instance not available for graceful shutdown.")

    # 3. BackendServiceDispatcher stoppen 
    if backend_service_dispatcher_instance: 
        logger.info("Stopping BackendServiceDispatcher...")
        try:
            await backend_service_dispatcher_instance.stop() 
            if message_processor_task and not message_processor_task.done():
                message_processor_task.cancel()
                try:
                    await asyncio.wait_for(message_processor_task, timeout=2.0)
                except asyncio.CancelledError:
                    logger.info("BackendServiceDispatcher task cancelled gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("BackendServiceDispatcher task did not stop cleanly within timeout.")
        except Exception as e:
            logger.error(f"Error stopping BackendServiceDispatcher: {str(e)}", exc_info=True)
    else:
        logger.warning("BackendServiceDispatcher instance not available or not initialized for graceful shutdown.")

    # 4. WebSocketManager herunterfahren (um alle von ihm verwalteten Verbindungen zu schließen)
    if websocket_manager_instance:
        logger.info("Shutting down WebSocketManager (closing all client connections)...")
        try:
            await websocket_manager_instance.stop() 
            logger.info("WebSocketManager shutdown complete.")
        except Exception as e:
            logger.error(f"Error during WebSocketManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("WebSocketManager instance not available for graceful shutdown.")

    # 5. app.state.websockets als letzte Bereinigung löschen (falls noch verwendet)
    remaining_websockets_count = len(app.state.websockets)
    if remaining_websockets_count > 0:
        logger.warning(f"{remaining_websockets_count} WebSocket connections still present in app.state.websockets. Attempting to force close.")
        for ws in list(app.state.websockets):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close(code=1001, reason="Server shutting down")
                    client_info = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
                    logger.debug(f"Forcibly closed WebSocket connection from app.state.websockets: {client_info}")
                else:
                    client_info = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
                    logger.debug(f"WebSocket already closed/disconnected in app.state.websockets: {client_info}")
            except RuntimeError as e:
                logger.warning(f"RuntimeError closing WebSocket during shutdown (likely already closed): {e}")
            except Exception as e:
                logger.error(f"Unexpected error during WebSocket force close in shutdown: {e}", exc_info=True)
            finally:
                app.state.websockets.discard(ws)

    logger.info(f"All WebSocket connections managed by WebSocketManager and app.state.websockets should be closed. Remaining in app.state.websockets: {len(app.state.websockets)}")
    logger.info("Application shutdown complete.")

# --- WebSocket-Endpunkt ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    logger.info(f"Incoming WebSocket connection for client_id: {client_id}")
    app.state.websockets.add(websocket) # Beibehalten, falls du dich noch für allgemeine Nachverfolgung darauf verlässt

    global websocket_manager_instance # Deklarieren, dass wir die globale Instanz verwenden

    if websocket_manager_instance: # Diese Prüfung ist jetzt robust
        try:
            await websocket_manager_instance.handle_connection(websocket, client_id)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for client_id: {client_id}")
        except Exception as e:
            logger.error(f"Error handling WebSocket connection for client_id {client_id}: {e}", exc_info=True)
        finally:
            app.state.websockets.discard(websocket) # Aus dem allgemeinen Tracking-Set entfernen
            logger.info(f"WebSocket connection for client_id {client_id} cleaned up from app.state.websockets.")
    else:
        logger.error("WebSocketManager not initialized when a connection attempted. Closing connection.")
        await websocket.close(code=1011, reason="Server internal error: WebSocketManager not ready.")


# --- Hauptausführungsblock (für direkte Skriptausführung mit Uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Running backend.py directly with Uvicorn.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
