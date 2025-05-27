# Backend/core/simulator.py

import asyncio
import random
import time
import logging
import uuid # This import is crucial and now correctly present
from typing import Dict, Union, Optional, Any
from fastapi import BackgroundTasks
from ..queues.shared_queue import MessageQueue
from ..models.message_types import QueueMessage

logger = logging.getLogger(__name__)

class SystemMessage:
    def __init__(self, type: str, data: Dict[str, Union[str, int, float]]):
        self.type = type
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format for queueing"""
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": time.time()
        }

class SimulationManager:
    def __init__(
        self,
        to_backend_queue: MessageQueue,
        to_frontend_queue: MessageQueue,
        from_backend_queue: MessageQueue,
        from_frontend_queue: MessageQueue,
        dead_letter_queue: MessageQueue
    ):
        self._running = False
        self.running = False
        self.counter = 0
        self.task = None
        self._autostart_enabled = False
        self._autostart_task = None
        self._to_backend_queue = to_backend_queue
        self._to_frontend_queue = to_frontend_queue
        self._from_backend_queue = from_backend_queue
        self._from_frontend_queue = from_frontend_queue
        self._dead_letter_queue = dead_letter_queue # Initialized dead_letter_queue.
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @is_ready.setter
    def is_ready(self, value: bool) -> None:
        old_value = self._is_ready
        self._is_ready = value
        logger.info(f"SimulationManager ready state changed from {old_value} to {value}")
        if value and self._autostart_enabled and not self.is_running:
            asyncio.create_task(self.start(client_id="autostart"))

    @property
    def is_running(self) -> bool:
        return self._running

    @is_running.setter
    def is_running(self, value: bool) -> None:
        self._running = value
        self.running = value
        logger.info(f"Simulation running state set to: {value}")

    async def start(self, client_id: str, background_tasks: Optional[BackgroundTasks] = None):
        """Start the simulation"""
        if self.running:
            status_msg = {
                "type": "status_update",
                "data": {"id": "simulation_status", "status": "already_running"},
                "client_id": client_id,
                "timestamp": time.time(),
                "id": str(uuid.uuid4()),
                "processing_path": [], "forwarding_path": []
            }
            await self._to_frontend_queue.enqueue(status_msg)
            return {"status": "already running"}

        await self._to_backend_queue.clear()
        await self._to_frontend_queue.clear()

        self.running = True
        if background_tasks:
            # Pass client_id to _run_simulation
            self.task = background_tasks.add_task(self._run_simulation, client_id)
        else:
            # FIX: Pass client_id when creating the task directly
            self.task = asyncio.create_task(self._run_simulation(client_id))
            
        system_msg = {
            "type": "system",
            "data": {
                "id": "sys_start",
                "message": "Simulation started via API",
                "status": "info"
            },
            "timestamp": time.time(),
            "client_id": client_id,
            "id": str(uuid.uuid4())
        }
        await self._to_frontend_queue.enqueue(system_msg)
        
        return {
            "status": "started",
            "message": "Simulation messages will begin flowing through queues"
        }

    def enable_autostart(self, enable: bool = True):
        """Enable or disable automatic simulation start"""
        self._autostart_enabled = enable
        if enable and not self._autostart_task:
            self._autostart_task = asyncio.create_task(self._autostart_check())
        elif not enable and self._autostart_task:
            self._autostart_task.cancel()
            self._autostart_task = None
        logger.info(f"Simulation autostart {'enabled' if enable else 'disabled'}")

    async def _autostart_check(self):
        """Periodically check if simulation should start automatically"""
        while self._autostart_enabled:
            try:
                if self.is_ready and not self.is_running:
                    logger.info("Autostart: Starting simulation")
                    await self.start(client_id="autostart")
                await asyncio.sleep(5)  # Check every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Autostart check failed: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def stop(self, client_id: Optional[str] = None):
        """Stop the simulation"""
        logger.info(f"Attempting to stop simulation for client: {client_id if client_id else 'N/A'}")

        if not self.running:
            logger.info("Simulation is not running. No action needed.")
            if client_id:
                status_msg = {
                    "type": "status_update",
                    "data": {"id": "sys_stop_failed", "message": "Simulation not running", "status": "info"},
                    "client_id": client_id,
                    "timestamp": time.time(),
                    "id": str(uuid.uuid4()),
                    "processing_path": [], "forwarding_path": []
                }
                await self._to_frontend_queue.enqueue(status_msg)
            return {"status": "not running"}

        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("Simulation task cancelled successfully.")
            except Exception as e:
                logger.error(f"Error while cancelling simulation task: {e}", exc_info=True)

        logger.info(f"Simulation stopped. Sending final status to client: {client_id if client_id else 'broadcast'}")
        system_msg_stopped = {
            "type": "status_update",
            "data": {
                "id": "sys_stop",
                "message": "Simulation stopped via API",
                "status": "stopped"
            },
            "timestamp": time.time(),
            "client_id": client_id if client_id else 'broadcast',
            "id": str(uuid.uuid4()),
            "processing_path": [], "forwarding_path": []
        }
        await self._to_frontend_queue.enqueue(system_msg_stopped)

        return {"status": "stopped"}

    async def status(self):
        """Get simulation status"""
        return {
            "running": self.running,
            "counter": self.counter,
            "timestamp": time.time(),
            "queues": {
                "to_frontend": self._to_frontend_queue.size(),
                "from_frontend": self._from_frontend_queue.size(),
                "to_backend": self._to_backend_queue.size(),
                "from_backend": self._from_backend_queue.size()
            }
        }

    async def _run_simulation(self, client_id: str): # This signature is correct!
        """Internal simulation task"""
        logger.info(f"Simulation task starting for client: {client_id}")
        
        try:
            system_init_msg = QueueMessage(
                type="system_init",
                data={
                    "id": "sys_init",
                    "message": "Simulation started by system",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time(),
                    "originating_client_id": client_id
                },
                timestamp=time.time(),
                processing_path=[],
                forwarding_path=[]
            ).dict()
            logger.debug(f"Created system message: {system_init_msg}")
            await self._to_backend_queue.enqueue(system_init_msg)
            logger.info("System message enqueued to backend queue")
        except Exception as e:
            logger.error(f"Failed to enqueue system message: {e}")
            raise
        
        while self.running:
            self.counter += 1
            await asyncio.sleep(1)
            
            sim_msg = QueueMessage(
                type="simulation_tick",
                data={
                    "id": f"sim_{self.counter}",
                    "content": f"Simulation message {self.counter}",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time(),
                    "client_id": client_id # client_id is now correctly in scope
                },
                timestamp=time.time(),
                processing_path=[],
                forwarding_path=[]
            ).dict()
            
            await self._to_backend_queue.enqueue(sim_msg)
            
            frontend_msg = {
                "type": "simulation_status",
                "data": {
                    "id": f"sim_{self.counter}",
                    "status": "running",
                    "progress": self.counter,
                    "client_id": client_id, # client_id is now correctly in scope
                    "timestamp": time.time()
                },
                "id": str(uuid.uuid4()),
                "processing_path": [], "forwarding_path": []
            }
            await self._to_frontend_queue.enqueue(frontend_msg)
            
            await asyncio.sleep(0.5 + 1.5 * random.random())
            
            if self.counter % 5 == 0:
                self._monitor_queues()
        
        logger.info(f"Simulation stopped for client: {client_id}")

        final_status_msg = {
            "type": "status_update",
            "data": {
                "id": "sys_final",
                "message": "Simulation loop finished",
                "status": "finished"
            },
            "timestamp": time.time(),
            "client_id": client_id,
            "id": str(uuid.uuid4()),
            "processing_path": [], "forwarding_path": []
        }
        await self._to_frontend_queue.enqueue(final_status_msg)

    def _monitor_queues(self):
        """Monitor queue health"""
        to_backend_size = self._to_backend_queue.size()
        from_backend_size = self._from_backend_queue.size()
        to_frontend_size = self._to_frontend_queue.size()
        from_frontend_size = self._from_frontend_queue.size()
        dead_letter_size = self._dead_letter_queue.size()

        logger.debug(f"Queue sizes: To-B: {to_backend_size}, From-B: {from_backend_size}, To-F: {to_frontend_size}, From-F: {from_frontend_size}, DLQ: {dead_letter_size}")

        if to_backend_size > 5:
            logger.warning(f"to_backend_queue has {to_backend_size} messages")
            try:
                oldest_msg = self._to_backend_queue._queue[0]
                age = time.time() - oldest_msg.get('timestamp', time.time())
                logger.warning(f"Oldest message age: {age:.2f}s (ID: {oldest_msg.get('data', {}).get('id')})")
            except Exception as e:
                logger.error(f"Error checking queue: {str(e)}")
                
        if (to_backend_size > 10 and 
            from_backend_size < 2):
            logger.warning("Messages accumulating in to_backend_queue without processing")
            
        if (from_backend_size > 5 and # Corrected variable name from 'from_backend_queue' to 'from_backend_size'
            to_frontend_size < 2):
            logger.warning("Messages not being forwarded to frontend")
