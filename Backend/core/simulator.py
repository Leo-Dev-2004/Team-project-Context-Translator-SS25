import asyncio
import random
import time
import logging
from typing import Dict
from fastapi import BackgroundTasks
from ..queues.shared_queue import to_backend_queue, to_frontend_queue
from ..models.message_types import SystemMessage, SimulationMessage

logger = logging.getLogger(__name__)

class SimulationManager:
    def __init__(self):
        self.running = False
        self.counter = 0

    async def start(self, background_tasks: BackgroundTasks = None):
        """Start the simulation"""
        if self.running:
            return {"status": "already running"}
        
        # Clear queues
        await to_backend_queue.clear()
        await to_frontend_queue.clear()
        
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
        await to_frontend_queue.enqueue(system_msg.dict())
        
        return {
            "status": "started",
            "message": "Simulation messages will begin flowing through queues"
        }

    async def stop(self):
        """Stop the simulation"""
        if not self.running:
            return {"status": "not running"}
            
        self.running = False
        
        # Send system notification
        system_msg = SystemMessage(
            type="system",
            data={
                "id": "sys_stop",
                "message": "Simulation stopped via API",
                "status": "info"
            }
        )
        await to_frontend_queue.enqueue(system_msg.dict())
        
        return {"status": "stopped"}

    async def status(self):
        """Get simulation status"""
        return {
            "running": self.running,
            "counter": self.counter,
            "timestamp": time.time()
        }

    async def simulate_entries(self):
        """Background task to simulate queue entries"""
        self.running = True
        logger.info("Simulation task starting")
        
        # Initial system message
        system_msg = SystemMessage(
            type="system",
            data={
                "id": "sys_init",
                "message": "Simulation started",
                "status": "pending"
            }
        )
        await to_backend_queue.enqueue(system_msg.dict())
        
        while self.running:
            self.counter += 1
            await asyncio.sleep(1)  # Generate messages every second
            
            # Create simulation message
            sim_msg = SimulationMessage(
                type="simulation",
                data={
                    "id": f"sim_{self.counter}",
                    "content": f"Simulation message {self.counter}",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time()
                }
            )
            
            await to_backend_queue.enqueue(sim_msg.dict())
            logger.info(f"Enqueued simulation message {self.counter}")
            
            # Random delay between 0.5-2 seconds
            await asyncio.sleep(0.5 + 1.5 * random.random())
        
        logger.info("Simulation stopped")
