from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import time
import uuid

# --- REVISED: PathEntry and its derivatives to match the expected dictionary structure ---
class ProcessingPathEntry(BaseModel):
    """Model for entries in the processing_path list."""
    # 'processor' is the key used in your MessageProcessor
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    completed_at: Optional[float] = None # This was in your log output for processed messages
    # 'details' could be added here if you need more structured custom data beyond status/completed_at

class ForwardingPathEntry(BaseModel):
    """Model for entries in the forwarding_path list."""
    # 'processor' is likely the key you'll use in QueueForwarder (or a similar descriptive name)
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    from_queue: Optional[str] = None # Matches the 'from_queue' key from your log
    to_queue: Optional[str] = None   # Matches the 'to_queue' key from your log

# --- END REVISED PathEntry Models ---

class QueueMessage(BaseModel):
    """Model for messages passing through internal queues"""
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    # UPDATED: Use the specific PathEntry models
    processing_path: List[ProcessingPathEntry] = Field(default_factory=list)
    forwarding_path: List[ForwardingPathEntry] = Field(default_factory=list)
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.timestamp()
        }
    )

# --- BaseMessage and derivatives (Kept as is, no changes needed here for the current problem) ---
class BaseMessage(BaseModel):
    type: str
    timestamp: float = Field(default_factory=time.time)
    status: str = "pending"
    # Keeping these as List[Dict[str, Any]] for BaseMessage if you need that flexibility for inherited models
    # However, for specific types like WebSocketMessage and QueueMessage, it's better to use the defined Pydantic models.
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

# --- Your primary WebSocket Message Model ---
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
    
    # UPDATED: Use the specific PathEntry models for WebSocketMessage
    processing_path: List[Union[ProcessingPathEntry, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Tracking of processing steps"
    )
    forwarding_path: List[Union[ForwardingPathEntry, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Tracking of queue forwarding steps"
    )
    # >>>>>>>>>>>>>>>>>> THIS IS THE CHANGE <<<<<<<<<<<<<<<<<<<<
    trace: Optional[Dict[str, Any]] = Field(  # Renamed from _trace to trace
        default_factory=dict,
        description="Internal tracing metadata",
        exclude=True  # Don't include in dict() by default
    )
    # >>>>>>>>>>>>>>>>>> END OF CHANGE <<<<<<<<<<<<<<<<<<<<

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
