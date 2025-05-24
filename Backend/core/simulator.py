import asyncio
import random
import time
import logging
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
        from_frontend_queue: MessageQueue
    ):
        self._running = False  # Private variable for internal state
        self.running = False   # Public attribute for compatibility
        self.counter = 0
        self.task = None
        self._to_backend_queue = to_backend_queue
        self._to_frontend_queue = to_frontend_queue
        self._from_backend_queue = from_backend_queue
        self._from_frontend_queue = from_frontend_queue
        self._is_ready = False  # Start as not ready by default

    @property
    def is_ready(self) -> bool:
        """Whether the simulation manager is ready to start"""
        return self._is_ready

    @is_ready.setter
    def is_ready(self, value: bool) -> None:
        """Set the ready status of the simulation manager"""
        self._is_ready = value
        logger.info(f"SimulationManager ready state set to: {value}")

    @property
    def is_running(self) -> bool:
        """Whether the simulation is currently running"""
        return self._running

    @is_running.setter
    def is_running(self, value: bool) -> None:
        """Set the running state of the simulation"""
        self._running = value
        self.running = value  # Keep public attribute in sync
        logger.info(f"Simulation running state set to: {value}")

    async def start(self, background_tasks: Optional[BackgroundTasks] = None):
        """Start the simulation"""
        if self.running:
            return {"status": "already running"}
        
        await self._to_backend_queue.clear()
        await self._to_frontend_queue.clear()
        
        self.running = True
        if background_tasks:
            self.task = background_tasks.add_task(self._run_simulation)
        else:
            self.task = asyncio.create_task(self._run_simulation())
            
        system_msg = {
            "type": "system",
            "data": {
                "id": "sys_start",
                "message": "Simulation started via API",
                "status": "info"
            },
            "timestamp": time.time()
        }
        await self._to_frontend_queue.enqueue(system_msg)
        
        return {
            "status": "started",
            "message": "Simulation messages will begin flowing through queues"
        }

    async def stop(self):
        """Stop the simulation"""
        if not self.running:
            return {"status": "not running"}
            
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        system_msg = {
            "type": "system",
            "data": {
                "id": "sys_stop",
                "message": "Simulation stopped via API",
                "status": "info"
            },
            "timestamp": time.time()
        }
        await self._to_frontend_queue.enqueue(system_msg)
        
        return {"status": "stopped"}

    async def status(self):
        """Get simulation status"""
        return {
            "running": self.running,
            "counter": self.counter,
            "timestamp": time.time(),
            "queues": {
                "to_frontend": self._to_frontend_queue.size(),
                "from_frontend": self._from_backend_queue.size(),
                "to_backend": self._to_backend_queue.size(),
                "from_backend": self._from_backend_queue.size()
            }
        }

    async def _run_simulation(self):
        """Internal simulation task"""
        logger.info("Simulation task starting")
        
        try:
            system_msg = QueueMessage(
                type="system",
                data={
                    "id": "sys_init",
                    "message": "Simulation started",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time()
                },
                timestamp=time.time(),
                processing_path=[],
                forwarding_path=[]
            ).dict()
            logger.debug(f"Created system message: {system_msg}")
            await self._to_backend_queue.enqueue(system_msg)
            logger.info("System message enqueued to backend queue")
        except Exception as e:
            logger.error(f"Failed to enqueue system message: {e}")
            raise
        
        while self.running:
            self.counter += 1
            await asyncio.sleep(1)
            
            sim_msg = QueueMessage(
                type="simulation",
                data={
                    "id": f"sim_{self.counter}",
                    "content": f"Simulation message {self.counter}",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time()
                },
                timestamp=time.time(),
                processing_path=[],
                forwarding_path=[]
            ).dict()
            await self._to_backend_queue.enqueue(sim_msg)
            
            await asyncio.sleep(0.5 + 1.5 * random.random())
            
            if self.counter % 5 == 0:
                self._monitor_queues()
        
        logger.info("Simulation stopped")

    def _monitor_queues(self):
        """Monitor queue health"""
        if self._to_backend_queue.size() > 5:
            logger.warning(f"to_backend_queue has {self._to_backend_queue.size()} messages")
            try:
                oldest_msg = self._to_backend_queue._queue[0]
                age = time.time() - oldest_msg.get('timestamp', time.time())
                logger.warning(f"Oldest message age: {age:.2f}s (ID: {oldest_msg.get('data', {}).get('id')}")
            except Exception as e:
                logger.error(f"Error checking queue: {str(e)}")
                
        if (self._to_backend_queue.size() > 10 and 
            self._from_backend_queue.size() < 2):
            logger.warning("Messages accumulating in to_backend_queue without processing")
            
        if (self._from_backend_queue.size() > 5 and 
            self._to_frontend_queue.size() < 2):
            logger.warning("Messages not being forwarded to frontend")
