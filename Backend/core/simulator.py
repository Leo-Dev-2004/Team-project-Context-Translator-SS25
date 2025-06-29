# Backend/core/SimulationManager.py

import asyncio
import random
import time
import logging
import uuid
from typing import Dict, Union, Optional
from fastapi import BackgroundTasks

# Import the MessageQueue for type hinting
from ..queues.MessageQueue import MessageQueue, AbstractMessageQueue

# Import the new UniversalMessage
from ..models.UniversalMessage import UniversalMessage, ProcessingPathEntry, ForwardingPathEntry

logger = logging.getLogger(__name__)

class SimulationManager:
    def __init__(self,
                 incoming_queue: AbstractMessageQueue,
                 outgoing_queue: AbstractMessageQueue,
                 websocket_out_queue: AbstractMessageQueue):
        self._running = False
        self.counter = 0
        self.task = None
        self._autostart_enabled = False
        self._autostart_task = None
        self._is_ready = False

        # Assign the passed queue instances
        self.incoming_queue = incoming_queue
        self.outgoing_queue = outgoing_queue
        self.websocket_out_queue = websocket_out_queue

        logger.info("SimulationManager initialized with provided queue instances.")

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
            status_msg = UniversalMessage(
                type="status.simulation_start",
                payload={"status": "already_running", "message": "Simulation is already running."},
                origin="simulation_manager",
                destination="frontend",
                client_id=client_id,
            )
            await self.outgoing_queue.enqueue(status_msg) # Use self.outgoing_queue
            return {"status": "already running"}

        self.running = True
        if background_tasks:
            self.task = background_tasks.add_task(self._run_simulation, client_id)
        else:
            self.task = asyncio.create_task(self._run_simulation(client_id))

        system_msg = UniversalMessage(
            type="system.simulation_start",
            payload={
                "message": "Simulation started via API",
                "status": "info"
            },
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id,
        )
        await self.outgoing_queue.enqueue(system_msg) # Use self.outgoing_queue

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
                    await self.start(client_id="autostart_system")
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Autostart check failed: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def stop(self, client_id: Optional[str] = None):
        """Stop the simulation"""
        logger.info(f"Attempting to stop simulation for client: {client_id if client_id else 'N/A'}")

        if not self._running:
            logger.info("Simulation is not running. No action needed.")
            status_msg = UniversalMessage(
                type="status.simulation_stop",
                payload={"message": "Simulation not running", "status": "info"},
                origin="simulation_manager",
                destination="frontend",
                client_id=client_id,
            )
            if client_id:
                await self.outgoing_queue.enqueue(status_msg) # Use self.outgoing_queue
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
        system_msg_stopped = UniversalMessage(
            type="status.simulation_stop",
            payload={
                "message": "Simulation stopped via API",
                "status": "stopped"
            },
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id if client_id else 'broadcast',
        )
        await self.outgoing_queue.enqueue(system_msg_stopped) # Use self.outgoing_queue

        return {"status": "stopped"}

    async def status(self):
        """Get simulation status"""
        # Use self.queue_name instead of global_queues.queue_name
        return {
            "running": self.running,
            "counter": self.counter,
            "timestamp": time.time(),
            "queues": {
                "incoming": self.incoming_queue.qsize() if self.incoming_queue else 0,
                "outgoing": self.outgoing_queue.qsize() if self.outgoing_queue else 0,
                "websocket_out": self.websocket_out_queue.qsize() if self.websocket_out_queue else 0,
            }
        }

    async def _run_simulation(self, client_id: str):
        """Internal simulation task"""
        logger.info(f"Simulation task starting for client: {client_id}")

        try:
            system_init_msg = UniversalMessage(
                type="system.simulation_initialization",
                payload={
                    "message": "Simulation started by system",
                    "status": "pending",
                    "progress": 0,
                    "created_at": time.time(),
                    "originating_client_id": client_id
                },
                origin="simulation_manager",
                destination="frontend",
                client_id=client_id,
            )
            logger.debug(f"Created system message: {system_init_msg.model_dump_json()}")
            await self.outgoing_queue.enqueue(system_init_msg) # Use self.outgoing_queue
            logger.info("System initialization message enqueued to outgoing queue")
        except Exception as e:
            logger.error(f"Failed to enqueue system initialization message: {e}")
            raise

        while self.running:
            self.counter += 1
            await asyncio.sleep(1)

            sim_msg_for_backend = UniversalMessage(
                type="simulation.tick_data",
                payload={
                    "content": f"Simulation data tick {self.counter}",
                    "simulation_counter": self.counter,
                    "created_at": time.time(),
                },
                origin="simulation_manager",
                destination="backend.data_processor",
                client_id=client_id,
            )
            await self.outgoing_queue.enqueue(sim_msg_for_backend) # Use self.outgoing_queue
            logger.debug(f"Simulation tick data (ID: {sim_msg_for_backend.id}) enqueued to outgoing for backend processing.")

            frontend_status_msg = UniversalMessage(
                type="status.simulation_progress",
                payload={
                    "status": "running",
                    "progress": self.counter,
                    "current_tick": self.counter,
                    "timestamp": time.time()
                },
                origin="simulation_manager",
                destination="frontend",
                client_id=client_id,
            )
            await self.outgoing_queue.enqueue(frontend_status_msg) # Use self.outgoing_queue
            logger.debug(f"Simulation status (ID: {frontend_status_msg.id}) enqueued to outgoing for frontend.")

            await asyncio.sleep(0.5 + 1.5 * random.random())

            if self.counter % 5 == 0:
                await self._monitor_queues()

        logger.info(f"Simulation stopped for client: {client_id}")

        final_status_msg = UniversalMessage(
            type="status.simulation_finished",
            payload={
                "message": "Simulation loop finished",
                "status": "finished",
                "final_tick_count": self.counter
            },
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id,
        )
        await self.outgoing_queue.enqueue(final_status_msg) # Use self.outgoing_queue

    async def _monitor_queues(self):
        """Monitor queue health (updated for new global queue names)"""
        # Use self.queue_name instead of global_queues.queue_name
        incoming_size = self.incoming_queue.qsize() if self.incoming_queue else 0
        outgoing_size = self.outgoing_queue.qsize() if self.outgoing_queue else 0
        websocket_out_size = self.websocket_out_queue.qsize() if self.websocket_out_queue else 0

        logger.debug(f"Queue sizes: Incoming: {incoming_size}, Outgoing: {outgoing_size}, WS_Out: {websocket_out_size}")

        if outgoing_size > 5:
            logger.warning(f"Outgoing queue has {outgoing_size} messages from simulation manager.")
            try:
                if hasattr(self.outgoing_queue, 'peek') and callable(self.outgoing_queue.peek):
                    oldest_msg = self.outgoing_queue.peek()
                    if oldest_msg:
                        age = time.time() - oldest_msg.timestamp
                        msg_id = oldest_msg.id
                        msg_type = oldest_msg.type
                        logger.warning(f"Oldest message in Outgoing: ID={msg_id}, Type={msg_type}, Age={age:.2f}s")
            except Exception as e:
                logger.error(f"Error checking oldest message in Outgoing queue: {str(e)}")

        if outgoing_size > 10 and websocket_out_size < 2:
            logger.warning("Messages accumulating in outgoing_queue, possibly due to slow MessageRouter or WebSocketManager.")

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
        status_msg = UniversalMessage(
            type="status.translation_settings_update",
            payload={"mode": mode, "context_level": context_level, "message": "Translation settings applied."},
            origin="simulation_manager",
            destination="frontend",
            client_id=client_id,
        )
        await self.outgoing_queue.enqueue(status_msg) # Use self.outgoing_queue
        pass