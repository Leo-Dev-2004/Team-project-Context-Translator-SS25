from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from ..core.simulator import SimulationManager
from ..core.processor import process_messages
from ..core.forwarder import forward_messages
from ..queues.shared_queue import (
    to_frontend_queue,
    from_frontend_queue,
    to_backend_queue,
    from_backend_queue
)
from ..services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

app = FastAPI()
sim_manager = SimulationManager()
ws_manager = WebSocketManager()

@app.on_event("startup")
async def startup_event():
    from ..queues.shared_queue import initialize_queues
    
    # Initialize all queues in the current event loop
    await initialize_queues()
    
    # Start core processing tasks
    asyncio.create_task(process_messages())
    asyncio.create_task(forward_messages())
    
    logger.info("Application startup complete with queues initialized")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000", "http://127.0.0.1:9000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Context Translator API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1"}

@app.get("/metrics")
async def get_metrics():
    return ws_manager.get_metrics()

@app.get("/simulation/start")
async def start_simulation(background_tasks: BackgroundTasks):
    return await sim_manager.start(background_tasks)

@app.get("/simulation/stop")
async def stop_simulation():
    return await sim_manager.stop()

@app.get("/simulation/status")
async def simulation_status():
    return await sim_manager.status()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.handle_connection(websocket)

