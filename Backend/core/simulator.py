# Backend/core/simulator.py (Refactored)

import asyncio
import random
import time
import logging
import uuid
from typing import Optional
from fastapi import BackgroundTasks

from ..queues.QueueTypes import AbstractMessageQueue
from ..models.UniversalMessage import UniversalMessage
from ..core.Queues import queues # Wir greifen direkt auf die globalen Queues zu

logger = logging.getLogger(__name__)

class SimulationManager:
    def __init__(self):
        # Der Manager holt sich die Queues, die er braucht, direkt.
        self._incoming_queue: AbstractMessageQueue = queues.incoming
        self._websocket_out_queue: AbstractMessageQueue = queues.websocket_out
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.counter = 0
        logger.info("SimulationManager initialized.")

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, client_id: str):
        if self._running:
            logger.warning(f"Simulation is already running. Start request for client {client_id} ignored.")
            return {"status": "already running"}

        self._running = True
        self._task = asyncio.create_task(self._run_simulation(client_id))
        logger.info(f"Simulation started for client {client_id}.")
        return {"status": "started"}

    async def stop(self, client_id: Optional[str] = None):
        if not self._running:
            logger.info("Simulation is not running. No action needed.")
            return {"status": "not running"}

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Simulation task cancelled successfully.")
        
        logger.info("Simulation stopped.")
        return {"status": "stopped"}

    async def status(self):
        return {
            "running": self._running,
            "counter": self.counter,
            "queues": {
                "incoming_size": self._incoming_queue.qsize(),
                "websocket_out_size": self._websocket_out_queue.qsize(),
            }
        }

    async def _run_simulation(self, client_id: str):
        logger.info(f"Simulation task starting for client: {client_id}")
        self.counter = 0

        while self._running:
            self.counter += 1
            await asyncio.sleep(random.uniform(1.0, 2.5))

            # 1. Erzeuge simulierte Rohdaten für die interne Verarbeitung
            simulated_stt_message = UniversalMessage(
                type="stt.transcription", # Wir simulieren eine echte Transkription
                payload={
                    "text": f"Das ist der simulierte Satz Nummer {self.counter}.",
                    "language": "de",
                    "confidence": round(random.uniform(0.85, 0.99), 2)
                },
                origin="simulation_manager",
                client_id=client_id,
                destination="backend.logic" # Ziel ist die interne Logik
            )
            # Sende sie in die INCOMING-Queue, damit der MessageRouter sie verarbeiten kann
            await self._incoming_queue.enqueue(simulated_stt_message)
            logger.debug(f"Simulator enqueued data tick #{self.counter} to incoming_queue.")

            # 2. Erzeuge ein Status-Update direkt für das Frontend
            frontend_status_msg = UniversalMessage(
                type="simulation.progress",
                payload={
                    "status": "running",
                    "current_tick": self.counter,
                    "timestamp": time.time()
                },
                origin="simulation_manager",
                destination=client_id, # Direkt an den anfragenden Client
                client_id=client_id
            )
            # Sende es in die WEBSOCKET_OUT-Queue, damit der WebSocketManager es zustellt
            await self._websocket_out_queue.enqueue(frontend_status_msg)
            logger.debug(f"Simulator enqueued progress update #{self.counter} to websocket_out_queue.")

        logger.info(f"Simulation loop finished for client: {client_id}")