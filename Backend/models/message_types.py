# Backend/models/message_types.py

from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import time
import uuid

# --- PathEntry Models for structured path tracking ---
class ProcessingPathEntry(BaseModel):
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    completed_at: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class ForwardingPathEntry(BaseModel):
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    from_queue: Optional[str] = None
    to_queue: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

# --- Internal Queue Message Model (now the primary base for queueable messages) ---
class QueueMessage(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str # This is explicitly required
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    processing_path: List[ProcessingPathEntry] = Field(default_factory=list)
    forwarding_path: List[ForwardingPathEntry] = Field(default_factory=list)
    client_id: Optional[str] = None
    from_queue: Optional[str] = None
    to_queue: Optional[str] = None

    def to_websocket_message(self) -> 'WebSocketMessage':
        # Ensure that path entries are converted to dicts if they are Pydantic models
        # This is important for JSON serialization before sending over WebSocket
        return WebSocketMessage(
            id=self.id,
            type=self.type,
            data=self.data,
            timestamp=self.timestamp,
            client_id=self.client_id,
            # Use model_dump() for converting Pydantic models to dictionaries for serialization
            processing_path=[entry.model_dump() if isinstance(entry, BaseModel) else entry for entry in self.processing_path],
            forwarding_path=[entry.model_dump() if isinstance(entry, BaseModel) else entry for entry in self.forwarding_path]
        )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.timestamp()
        }
    )

# --- Specific Message Types (now inheriting from QueueMessage) ---
# Removed BaseMessage as its fields are now covered by QueueMessage for queueable messages.
# If you have messages that are NOT meant for queues but still need a 'base',
# you might reintroduce a simpler BaseModel for them.
# For now, all these are QueueMessage types.

class SystemMessage(QueueMessage): # Inherit from QueueMessage
    """Messages for internal system communications or general updates."""
    # Specific fields can be added here if needed, in addition to QueueMessage fields
    pass

class SimulationMessage(QueueMessage): # Inherit from QueueMessage
    """Messages specifically related to simulation control or data."""
    # Specific fields can be added here if needed
    pass

class FrontendMessage(QueueMessage): # Inherit from QueueMessage
    """Messages originating from the frontend (e.g., user commands)."""
    # Specific fields can be added here if needed
    pass

class BackendProcessedMessage(QueueMessage): # Inherit from QueueMessage
    """Messages representing work processed by the backend, often with progress."""
    progress: Optional[int] = None # Adds a specific field to QueueMessage

# --- Dead Letter Message Model ---
class DeadLetterMessage(QueueMessage):
    """Model for messages sent to the Dead Letter Queue."""
    original_message: Dict[str, Any]
    reason: str
    dlq_timestamp: float = Field(default_factory=time.time)
    error_details: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    @classmethod
    def set_dlq_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Ensure 'type' is set for DeadLetterMessage
            if 'type' not in data:
                data['type'] = "dead_letter_entry"

            # Ensure 'data' field (from QueueMessage) is populated with relevant info
            # Only set if 'data' is not already explicitly provided
            if 'data' not in data and 'original_message' in data and 'reason' in data:
                original_msg = data['original_message']
                reason_str = data['reason']
                data['data'] = {
                    "reason": reason_str,
                    "original_message_type": original_msg.get("type", "unknown"),
                    "original_message_id": original_msg.get("id", "unknown_id"),
                    # Use a safer default for 'data' key if 'data' is missing
                    "original_message_summary": original_msg.get("data", {}).get("command", original_msg.get("data", {}).get("message", "N/A_summary"))
                }
            # The 'id' and 'timestamp' fields will be handled by QueueMessage's default_factory
            # if not explicitly provided during instantiation.

        return data


# --- WebSocket Message Model ---
class ErrorTypes(str, Enum):
    VALIDATION = "error_validation"
    COMMAND_NOT_FOUND = "error_command_not_found"
    SIMULATION_FAILED = "error_simulation_failed"
    QUEUE_FULL = "error_queue_full"
    INTERNAL = "error_internal"
    CONNECTION = "error_connection"
    UNKNOWN_MESSAGE_TYPE = "error_unknown_message_type"

class WebSocketMessage(BaseModel):
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the message"
    )
    type: str = Field(
        ...,
        description="Message type is required (e.g. 'command', 'data', 'status')",
        examples=["command", "data", "status"]
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Message payload data",
        examples=[{"command": "start_simulation"}, {"message": "Hello"}]
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp of message creation"
    )
    client_id: Optional[str] = Field(
        None,
        description="Optional client identifier",
        examples=["client_123", "another_client_id"]
    )
    # Changed path types to always expect Pydantic models (or dicts after model_dump)
    processing_path: List[Union[ProcessingPathEntry, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Tracking of processing steps"
    )
    forwarding_path: List[Union[ForwardingPathEntry, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Tracking of queue forwarding steps"
    )
    trace: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Internal tracing metadata",
        exclude=True
    )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.timestamp()
        },
        json_schema_extra={
            "examples": [
                {
                    "type": "command",
                    "data": {"command": "start_simulation"},
                    "timestamp": 1716316800.0,
                    "client_id": "client_123"
                },
                {
                    "type": "status",
                    "data": {"status": "running", "progress": 50},
                    "timestamp": 1716316801.0,
                    "client_id": "client_abc"
                }
            ]
        }
    )