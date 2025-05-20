import asyncio
import random
import time
import logging
from typing import Dict, Union, Optional, Any
from fastapi import BackgroundTasks
from ..queues.shared_queue import MessageQueue
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_backend_queue,
)

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
        from_backend_queue: MessageQueue
    ):
        self.running = False
        self.counter = 0
        self._to_backend_queue = to_backend_queue
        self._to_frontend_queue = to_frontend_queue
        self._from_backend_queue = from_backend_queue

    async def start(self, background_tasks: Optional[BackgroundTasks] = None):
        """Start the simulation"""
        if self.running:
            return {"status": "already running"}
        
        # Clear queues using instance queues
        await self._to_backend_queue.clear()
        await self._to_frontend_queue.clear()
        
        # Start simulation task
        if background_tasks:
            background_tasks.add_task(self.simulate_entries)
        else:
            asyncio.create_task(self.simulate_entries())
            
        # Send system notification
        system_msg = SystemMessage(
            type="system",
            data={
                "id": "sys_start",
                "message": "Simulation started via API",
                "status": "info"
            }
        )
        await self._to_frontend_queue.enqueue(system_msg.to_dict())
        
        return {
            "status": "started",
            "message": "Simulation messages will begin flowing through queues"
        }

    async def stop(self):
        """Stop the simulation"""
        if not self.running:
            return {"status": "not running"}
            
        self.running = False
        
        # Send system notification using instance queue
        system_msg = SystemMessage(
            type="system",
            data={
                "id": "sys_stop",
                "message": "Simulation stopped via API",
                "status": "info"
            }
        )
        await self._to_frontend_queue.enqueue(system_msg.to_dict())
        
        return {"status": "stopped"}

    async def status(self):
        """Get simulation status"""
        return {
            "running": self.running,
            "counter": self.counter,
            "timestamp": time.time()
        }

    def validate_message(self, msg: dict) -> bool:
        """Validate message structure"""
        required_fields = {'type', 'data', 'timestamp'}
        return all(field in msg for field in required_fields)

    async def simulate_entries(self):
        """Background task to simulate queue entries"""
        self.running = True
        logger.info("Simulation task starting")

        # Enhanced queue monitoring using instance queues
        def monitor_queues():
            if self._to_backend_queue.size() > 5:
                logger.warning(f"to_backend_queue has {self._to_backend_queue.size()} messages")
                try:
                    oldest_msg = self._to_backend_queue._queue[0]
                    age = time.time() - oldest_msg.get('timestamp', time.time())
                    logger.warning(f"Oldest message age: {age:.2f}s (ID: {oldest_msg.get('data', {}).get('id')}")
                except Exception as e:
                    logger.error(f"Error checking queue: {str(e)}")
        
        # Initial system message
        system_msg = SystemMessage(
            type="system",
            data={
                "id": "sys_init",
                "message": "Simulation started",
                "status": "pending"
            }
        )
        await self._to_backend_queue.enqueue(system_msg.to_dict())
        
        while self.running:
            self.counter += 1
            await asyncio.sleep(1)  # Generate messages every second
            
            # Create simulation message
            sim_msg = SystemMessage(
                type="simulation",
                data={
                    "id": f"sim_{self.counter}",
                    "content": f"Simulation message {self.counter}",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time()
                }
            )
            
            await self._to_backend_queue.enqueue(sim_msg.to_dict())
            logger.info(f"Enqueued simulation message {self.counter}")
            
            # Random delay between 0.5-2 seconds
            await asyncio.sleep(0.5 + 1.5 * random.random())
            
            # Monitor queue health periodically
            if self.counter % 5 == 0:  # Every 5 messages
                monitor_queues()
                
                # Check if messages are being processed
                if (self._to_backend_queue.size() > 10 and 
                    self._from_backend_queue.size() < 2):
                    logger.warning("Messages accumulating in to_backend_queue without processing")
                
                # Check if messages are reaching frontend
                if (self._from_backend_queue.size() > 5 and 
                    self._to_frontend_queue.size() < 2):
                    logger.warning("Messages not being forwarded to frontend")
        
        logger.info("Simulation stopped")
