# Backend/core/simulator.py

import asyncio
import random
import time
import logging
import uuid
from typing import Dict, Union, Optional, Any
from fastapi import BackgroundTasks

# Import the global queues instance
from Backend.core.Queues import queues as global_queues # Renamed to avoid conflict

# Import the new UniversalMessage
from Backend.models.UniversalMessage import UniversalMessage, ProcessingPathEntry, ForwardingPathEntry
# Removed: from Backend.queues.queue_types import AbstractMessageQueue
# Removed: from ..queues.MessageQueue import MessageQueue
# Removed: from ..models.message_types import QueueMessage
# Removed: class SystemMessage (will be replaced by UniversalMessage)


logger = logging.getLogger(__name__)

class SimulationManager:
    # Removed queue parameters from __init__
    def __init__(self):
        self._running = False
        self.counter = 0
        self.task = None
        self._autostart_enabled = False
        self._autostart_task = None
        self._is_ready = False

        # Directly use the global queues instance
        # The simulator primarily produces messages for the outgoing queue
        self._outgoing_queue = global_queues.outgoing
        self._dead_letter_queue = global_queues.dead_letter
        # If the simulator needs to receive specific internal messages from a backend service,
        # it would get them via the BackendServiceDispatcher which pulls from global_queues.incoming
        # So, no direct "from_backend_queue" here anymore.

        logger.info("SimulationManager initialized with global queues references.")



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
        self.running = value # Keep this for compatibility if internal logic relies on `self.running` directly
        logger.info(f"Simulation running state set to: {value}")

    async def start(self, client_id: str, background_tasks: Optional[BackgroundTasks] = None):
        """Start the simulation"""
        if self.running:
            status_msg = UniversalMessage( # Now UniversalMessage
                type="status.simulation_start", # More specific type
                payload={"status": "already_running", "message": "Simulation is already running."}, # Renamed 'data' to 'payload'
                origin="simulation_manager",
                destination="frontend", # Explicit destination for the router
                client_id=client_id,
                # id, timestamp, processing_path, forwarding_path will be default_factory
            )
            await self._outgoing_queue.enqueue(status_msg) # Enqueue to the central outgoing queue
            return {"status": "already running"}

        # Draining global queues directly might be problematic for other services.
        # If a fresh state is needed, it should be managed by the queue consumers (Dispatcher, Router)
        # or a specific reset mechanism for the queues themselves.
        # For now, removed these specific drain calls. If needed, we'd drain the specific
        # output queue for the simulator, which is _outgoing_queue.
        # await self._to_backend_queue.drain() # Removed
        # await self._to_frontend_queue.drain() # Removed


        self.running = True
        if background_tasks:
            self.task = background_tasks.add_task(self._run_simulation, client_id)
        else:
            self.task = asyncio.create_task(self._run_simulation(client_id))

        system_msg = UniversalMessage( # Now UniversalMessage
            type="system.simulation_start", # More specific type
            payload={ # Renamed 'data' to 'payload'
                "message": "Simulation started via API",
                "status": "info"
            },
            origin="simulation_manager",
            destination="frontend", # Explicit destination
            client_id=client_id,
        )
        await self._outgoing_queue.enqueue(system_msg) # Enqueue to the central outgoing queue

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
                    # Autostart should also specify a client_id for traceability
                    await self.start(client_id="autostart_system")
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
            # Send status update
            status_msg = UniversalMessage( # Now UniversalMessage
                type="status.simulation_stop", # More specific type
                payload={"message": "Simulation not running", "status": "info"},
                origin="simulation_manager",
                destination="frontend",
                client_id=client_id,
            )
            if client_id: # Only send to specific client if provided
                await self._outgoing_queue.enqueue(status_msg)
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
        system_msg_stopped = UniversalMessage( # Now UniversalMessage
            type="status.simulation_stop", # More specific type
            payload={
                "message": "Simulation stopped via API",
                "status": "stopped"
            },
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id if client_id else 'broadcast', # Use actual client_id or 'broadcast'
        )
        await self._outgoing_queue.enqueue(system_msg_stopped) # Enqueue to the central outgoing queue

        return {"status": "stopped"}

    async def status(self):
        """Get simulation status"""
        # Updated to reflect new global queue names
        return {
            "running": self.running,
            "counter": self.counter,
            "timestamp": time.time(),
            "queues": {
                "incoming": global_queues.incoming.qsize() if global_queues.incoming else 0,
                "outgoing": global_queues.outgoing.qsize() if global_queues.outgoing else 0,
                "websocket_out": global_queues.websocket_out.qsize() if global_queues.websocket_out else 0,
                "dead_letter": global_queues.dead_letter.qsize() if global_queues.dead_letter else 0,
            }
        }

    async def _run_simulation(self, client_id: str):
        """Internal simulation task"""
        logger.info(f"Simulation task starting for client: {client_id}")

        try:
            # Initial system message (e.g., to backend dispatcher for setup)
            system_init_msg = UniversalMessage(
                type="system.simulation_initialization", # More specific type
                payload={ # Renamed 'data' to 'payload'
                    "message": "Simulation started by system",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time(),
                    "originating_client_id": client_id
                },
                origin="simulation_manager",
                # This message's destination might be another backend service for setup,
                # or directly to frontend if it's purely a status for client.
                # Assuming for now it's a status update for the frontend.
                destination="frontend",
                client_id=client_id, # Link back to the client that initiated it
                # paths will be default_factory
            )
            logger.debug(f"Created system message: {system_init_msg.model_dump_json()}")
            await self._outgoing_queue.enqueue(system_init_msg) # Enqueue to outgoing
            logger.info("System initialization message enqueued to outgoing queue")
        except Exception as e:
            logger.error(f"Failed to enqueue system initialization message: {e}")
            raise

        while self.running:
            self.counter += 1
            await asyncio.sleep(1)

            # Simulation tick message for backend processing (if any)
            # This would typically go to a backend service for processing
            sim_msg_for_backend = UniversalMessage(
                type="simulation.tick_data", # More specific type
                payload={ # Renamed 'data' to 'payload'
                    "content": f"Simulation data tick {self.counter}",
                    "simulation_counter": self.counter,
                    "created_at": time.time(),
                },
                origin="simulation_manager",
                destination="backend.data_processor", # Example: send to a specific backend service
                client_id=client_id, # Maintain client context
            )
            await self._outgoing_queue.enqueue(sim_msg_for_backend)
            logger.debug(f"Simulation tick data (ID: {sim_msg_for_backend.id}) enqueued to outgoing for backend processing.")


            # Simulation status update for frontend
            frontend_status_msg = UniversalMessage(
                type="status.simulation_progress", # More specific type
                payload={ # Renamed 'data' to 'payload'
                    "status": "running",
                    "progress": self.counter,
                    "current_tick": self.counter,
                    "timestamp": time.time()
                },
                origin="simulation_manager",
                destination="frontend", # Explicitly for the frontend
                client_id=client_id, # Link back to the client
            )
            await self._outgoing_queue.enqueue(frontend_status_msg)
            logger.debug(f"Simulation status (ID: {frontend_status_msg.id}) enqueued to outgoing for frontend.")


            await asyncio.sleep(0.5 + 1.5 * random.random())

            if self.counter % 5 == 0:
                await self._monitor_queues()

        logger.info(f"Simulation stopped for client: {client_id}")

        final_status_msg = UniversalMessage(
            type="status.simulation_finished", # More specific type
            payload={ # Renamed 'data' to 'payload'
                "message": "Simulation loop finished",
                "status": "finished",
                "final_tick_count": self.counter
            },
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id,
        )
        await self._outgoing_queue.enqueue(final_status_msg) # Enqueue to outgoing

    async def _monitor_queues(self):
        """Monitor queue health (updated for new global queue names)"""
        # Ensure global_queues are initialized before trying to access qsize
        incoming_size = global_queues.incoming.qsize() if global_queues.incoming else 0
        outgoing_size = global_queues.outgoing.qsize() if global_queues.outgoing else 0
        websocket_out_size = global_queues.websocket_out.qsize() if global_queues.websocket_out else 0
        dead_letter_size = global_queues.dead_letter.qsize() if global_queues.dead_letter else 0

        logger.debug(f"Queue sizes: Incoming: {incoming_size}, Outgoing: {outgoing_size}, WS_Out: {websocket_out_size}, DLQ: {dead_letter_size}")

        if outgoing_size > 5: # Monitor outgoing queue as it's the simulator's primary output
            logger.warning(f"Outgoing queue has {outgoing_size} messages from simulation manager.")
            try:
                # Peek logic requires a peek() method on your MessageQueue,
                # which isn't standard for asyncio.Queue. Assuming it exists.
                if hasattr(global_queues.outgoing, 'peek') and callable(global_queues.outgoing.peek):
                    oldest_msg = global_queues.outgoing.peek()
                    if oldest_msg:
                        age = time.time() - oldest_msg.timestamp
                        msg_id = oldest_msg.id
                        msg_type = oldest_msg.type
                        logger.warning(f"Oldest message in Outgoing: ID={msg_id}, Type={msg_type}, Age={age:.2f}s")
            except Exception as e:
                logger.error(f"Error checking oldest message in Outgoing queue: {str(e)}")

        # Adjust warnings based on the new flow
        if outgoing_size > 10 and websocket_out_size < 2:
            logger.warning("Messages accumulating in outgoing_queue, possibly due to slow MessageRouter or WebSocketManager.")

        # Note: The simulator doesn't directly interact with incoming or websocket_out for its core logic,
        # so detailed warnings about those queues might be better placed in MessageRouter or WebSocketManager.
        # This monitor is primarily for the simulator's *own* output and the overall system health.

    async def set_translation_settings(self, mode: str, context_level: int, client_id: str):
        """
        Sets the translation settings for the simulation.
        :param mode: The translation mode (e.g., "formal", "informal").
        :param context_level: The level of context to consider (e.g., 1, 2, 3).
        :param client_id: The ID of the client requesting the change.
        """
        self._translation_mode = mode
        self._context_level = context_level
        logger.info(f"Translation settings updated for client {client_id}: Mode='{mode}', Context Level={context_level}")
        # Send a status update about this setting change
        status_msg = UniversalMessage(
            type="status.translation_settings_update",
            payload={"mode": mode, "context_level": context_level, "message": "Translation settings applied."},
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id,
        )
        await self._outgoing_queue.enqueue(status_msg)
        pass # The actual logic to apply settings would go here.