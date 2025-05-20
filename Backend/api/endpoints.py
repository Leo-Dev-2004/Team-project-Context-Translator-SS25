from fastapi import FastAPI, WebSocket, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from typing import Optional
from ..core.simulator import SimulationManager
from ..core.processor import process_messages
from ..core.forwarder import forward_messages
from ..queues.shared_queue import get_initialized_queues
from ..services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

app = FastAPI()
ws_manager = WebSocketManager()
sim_manager: Optional[SimulationManager] = None

async def get_simulation_manager() -> SimulationManager:
    """Dependency to get initialized SimulationManager"""
    if sim_manager is None:
        raise RuntimeError("SimulationManager not initialized")
    return sim_manager

@app.on_event("startup")
async def startup_event():
    global sim_manager
    
    # Initialize all queues
    await get_initialized_queues()
    
    # Initialize SimulationManager with initialized queues
    sim_manager = SimulationManager(
        to_backend_queue=get_to_backend_queue(),
        to_frontend_queue=get_to_frontend_queue(),
        from_backend_queue=get_from_backend_queue()
    )
    
    # Start core processing tasks
    asyncio.create_task(process_messages())
    asyncio.create_task(forward_messages())
    
    logger.info("Application startup complete with queues and SimulationManager initialized")

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
async def start_simulation(
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    return await manager.start(background_tasks)

@app.get("/simulation/stop")
async def stop_simulation(
    manager: SimulationManager = Depends(get_simulation_manager)
):
    return await manager.stop()

@app.get("/simulation/status")
async def simulation_status(
    manager: SimulationManager = Depends(get_simulation_manager)
):
    return await manager.status()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.handle_connection(websocket)

