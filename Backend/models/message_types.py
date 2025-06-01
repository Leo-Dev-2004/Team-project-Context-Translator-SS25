from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import time
import uuid

# --- PathEntry Models for structured path tracking ---
class ProcessingPathEntry(BaseModel):
    """Model for entries in the processing_path list."""
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    completed_at: Optional[float] = None
    details: Optional[Dict[str, Any]] = None # Added for more flexibility

class ForwardingPathEntry(BaseModel):
    """Model for entries in the forwarding_path list."""
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    from_queue: Optional[str] = None
    to_queue: Optional[str] = None
    details: Optional[Dict[str, Any]] = None # Added for more flexibility

# --- Base Message Models ---
class BaseMessage(BaseModel):
    type: str
    timestamp: float = Field(default_factory=time.time)
    status: str = "pending"
    # These base fields are kept flexible for inherited models if they need varied dict/Pydantic types
    processing_path: List[Dict[str, Any]] = Field(default_factory=list)
    forwarding_path: List[Dict[str, Any]] = Field(default_factory=list)

class SystemMessage(BaseMessage):
    data: Dict[str, Any]

class SimulationMessage(BaseMessage):
    data: Dict[str, Any]

class FrontendMessage(BaseMessage):
    data: Dict[str, Any]

class BackendProcessedMessage(BaseMessage):
    data: Dict[str, Any]
    progress: Optional[int] = None

# --- Internal Queue Message Model ---
class QueueMessage(BaseModel):
    """Model for messages passing through internal queues."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    processing_path: List[ProcessingPathEntry] = Field(default_factory=list) # Specific Pydantic model
    forwarding_path: List[ForwardingPathEntry] = Field(default_factory=list) # Specific Pydantic model
    client_id: Optional[str] = None # Added as QueueMessage might carry client_id for routing

    def to_websocket_message(self) -> 'WebSocketMessage':
        """Converts a QueueMessage to a WebSocketMessage."""
        return WebSocketMessage(
            id=self.id,
            type=self.type,
            data=self.data,
            timestamp=self.timestamp,
            client_id=self.client_id,
            processing_path=self.processing_path,
            forwarding_path=self.forwarding_path
        )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.timestamp()
        }
    )

# --- Dead Letter Message Model ---
class DeadLetterMessage(QueueMessage): # Inherit from QueueMessage
    """Model for messages sent to the Dead Letter Queue."""
    original_message: Dict[str, Any]  # The raw dictionary of the message that failed
    reason: Optional[str]                       # Why it failed
    dlq_timestamp: float = Field(default_factory=time.time) # When it entered the DLQ
    error_details: Optional[Dict[str, Any]] = None # Additional details about the error

    # Custom __init__ to set default fields for QueueMessage and manage original_message
    def __init__(self, original_message: Dict[str, Any], reason: str, **data):
        # Set default type for DLQ entries
        # Populate base data with summary info, keeping full original_message separate
        super().__init__(
            type="dead_letter_entry",
            data={
                "reason": reason,
                "original_message_type": original_message.get("type", "unknown"),
                "original_message_id": original_message.get("id", "unknown_id"),
                "original_message_summary": original_message.get("data", {}).get("command", original_message.get("data", {}).get("message", "N/A_summary")) # Small summary
            },
            # Pass through any other fields provided in **data that QueueMessage expects
            **{k: v for k, v in data.items() if k in ['id', 'timestamp', 'client_id', 'processing_path', 'forwarding_path']}
        )
        self.original_message = original_message
        self.reason = reason
        self.dlq_timestamp = data.get("dlq_timestamp", time.time())
        self.error_details = data.get("error_details", None)

        # Ensure ID is always set, even if base class somehow didn't set it (e.g., if 'id' was None in data)
        if not self.id:
            self.id = str(uuid.uuid4())


# --- WebSocket Message Model ---
class ErrorTypes(str, Enum):
    VALIDATION = "error_validation"
    COMMAND_NOT_FOUND = "error_command_not_found"
    SIMULATION_FAILED = "error_simulation_failed"
    QUEUE_FULL = "error_queue_full"
    INTERNAL = "error_internal"
    CONNECTION = "error_connection"

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
    processing_path: List[Union[ProcessingPathEntry, Dict[str, Any]]] = Field( # Allow dicts for flexibility on ingress
        default_factory=list,
        description="Tracking of processing steps"
    )
    forwarding_path: List[Union[ForwardingPathEntry, Dict[str, Any]]] = Field( # Allow dicts for flexibility on ingress
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
