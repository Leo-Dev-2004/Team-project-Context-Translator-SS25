# Backend/models/UniversalMessage.py

from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, model_validator, ValidationError # Added ValidationError
from typing import Optional, List, Dict, Any, Union
import time
import uuid

# --- PathEntry Models for structured path tracking ---
class ProcessingPathEntry(BaseModel):
    processor: str
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp when processing started/recorded.")
    status: Optional[str] = Field(None, description="Current status of the processing step (e.g., 'started', 'completed', 'failed').")
    completed_at: Optional[float] = Field(None, description="Unix timestamp when processing step was completed, if applicable.")
    details: Optional[Dict[str, Any]] = Field(None, description="Any additional, relevant details from the processor.")

class ForwardingPathEntry(BaseModel):
    router: str = "MessageRouter" # Explicitly state the component responsible for forwarding
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp when forwarding decision/action occurred.")
    from_queue: Optional[str] = Field(None, description="Name of the queue the message was dequeued from (e.g., 'outgoing').")
    to_queue: Optional[str] = Field(None, description="Name of the queue the message was enqueued to (e.g., 'websocket_out', 'dead_letter').")
    details: Optional[Dict[str, Any]] = Field(None, description="Any additional, relevant details from the router/forwarder.")

# --- The ONE Universal Message Model ---
class UniversalMessage(BaseModel):
    """
    The **universal message format** used throughout the entire backend system
    and for communication with the frontend via WebSockets.
    This single type replaces all previous specific message classes (SystemMessage, SimulationMessage, etc.).
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the message.")
    type: str = Field(..., description="Categorical type of the message (e.g., 'command.start_simulation', 'status.translation_progress', 'error.internal').")
    payload: Dict[str, Any] = Field(default_factory=dict, description="The actual data payload of the message. Content varies based on 'type'.")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of message creation.")

    origin: Optional[str] = Field(None, description="Identifier of the component that originated this message (e.g., 'frontend', 'simulation_manager', 'translation_service').")
    destination: Optional[str] = Field(None, description="Intended next recipient/destination for routing (e.g., 'backend.dispatcher', 'frontend', 'dead_letter_queue').")

    client_id: Optional[str] = Field(None, description="Optional identifier for the client associated with this message, primarily for WebSocket clients.")

    # Path tracking for debugging and auditing
    processing_path: List[ProcessingPathEntry] = Field(default_factory=list, description="Ordered list of processing steps the message has undergone.")
    forwarding_path: List[ForwardingPathEntry] = Field(default_factory=list, description="Ordered list of queue forwarding steps the message has undergone.")

    trace: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Internal tracing metadata, excluded from default serialization.", exclude=True)

    model_config = ConfigDict(
        populate_by_name=True, # Allow field names or aliases for population
        extra='forbid', # Disallow extra fields not defined in the model
        json_schema_extra={
            "examples": [
                {
                    "type": "command.start_simulation",
                    "payload": {"param1": "value1", "speed": 1.5},
                    "origin": "frontend",
                    "destination": "backend.dispatcher",
                    "client_id": "client_abc-123"
                },
                {
                    "type": "status.translation_progress",
                    "payload": {"progress": 75, "current_segment": "Hello world!"},
                    "origin": "translation_service",
                    "destination": "frontend",
                    "client_id": "client_abc-123",
                    "processing_path": [
                        {"processor": "translation_service", "status": "processing"}
                    ]
                }
            ]
        }
    )

    # The `to_websocket_message` method is no longer strictly necessary
    # if `WebSocketMessage` just inherits from `UniversalMessage`.
    # A `UniversalMessage` instance can be directly serialized to JSON.
    # However, if you explicitly want a method for clarity or future specific serialization,
    # it would effectively return a `WebSocketMessage` instance (which is itself a UniversalMessage).
    def to_websocket_message(self) -> 'WebSocketMessage':
        """
        Converts this UniversalMessage to a WebSocketMessage.
        Since WebSocketMessage now inherits directly from UniversalMessage,
        this effectively returns a validated copy of itself as a WebSocketMessage.
        """
        return WebSocketMessage.model_validate(self.model_dump())

# --- WebSocket Message Model ---
class WebSocketMessage(UniversalMessage):
    """
    Represents a message specifically for WebSocket communication.
    It **inherits directly from UniversalMessage**, meaning any UniversalMessage
    can be sent over the WebSocket. This class primarily serves as a clear
    type hint for the WebSocket Manager and for OpenAPI schema generation
    at the API boundary. No new fields are typically needed here.
    """
    # No new fields are added, but the examples are tailored for WebSocket context.
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "abc-123",
                    "type": "command.start_simulation",
                    "payload": {"param1": "value1"},
                    "timestamp": 1678886400.0,
                    "origin": "frontend",
                    "destination": "backend.dispatcher",
                    "client_id": "client_abc-123",
                    "processing_path": [],
                    "forwarding_path": []
                },
                {
                    "id": "def-456",
                    "type": "status.translation_progress",
                    "payload": {"progress": 75, "current_segment": "Hello world!"},
                    "timestamp": 1678886401.0,
                    "origin": "translation_service",
                    "destination": "frontend",
                    "client_id": "client_abc-123",
                    "processing_path": [
                        {"processor": "translation_service", "timestamp": 1678886400.5, "status": "processing"}
                    ],
                    "forwarding_path": [
                        {"router": "MessageRouter", "timestamp": 1678886400.8, "from_queue": "outgoing", "to_queue": "websocket_out"}
                    ]
                }
            ]
        }
    )

# --- Error Types Enum ---
class ErrorTypes(str, Enum):
    """Standardized error types for consistent error messaging."""
    VALIDATION = "error.validation"
    COMMAND_NOT_FOUND = "error.command_not_found"
    SIMULATION_FAILED = "error.simulation_failed"
    QUEUE_OVERLOAD = "error.queue_overload"
    INTERNAL_SERVER_ERROR = "error.internal_server"
    CONNECTION_ERROR = "error.connection"
    UNKNOWN_MESSAGE_TYPE = "error.unknown_message_type"
    AUTHENTICATION_FAILED = "error.authentication_failed"
    PERMISSION_DENIED = "error.permission_denied"
    UNKNOWN_ERROR = "error.unknown"
    MESSAGE_UNDELIVERABLE = "error.message_undeliverable"
    INVALID_MESSAGE_FORMAT = "error.invalid_message_format"
    QUEUE_OPERATION_FAILED = "error.queue_operation_failed"
    SYSTEM_ERROR= "error.system_error"
    ROUTING_ERROR = "error.routing_error"
    VALIDATION_ERROR = "error.message_validation"
    PROCESSING_ERROR = "error.processing"
