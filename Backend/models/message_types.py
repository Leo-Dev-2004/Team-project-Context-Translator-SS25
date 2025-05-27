# Backend/models/message_types.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import time
import uuid

class PathEntry(BaseModel):
    """Base model for tracking message processing steps"""
    processor: str
    timestamp: float = Field(default_factory=time.time)
    status: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class ProcessingPathEntry(PathEntry):
    """Model for processing path entries"""
    completed_at: Optional[float] = None

class ForwardingPathEntry(PathEntry):
    """Model for forwarding path entries"""
    from_queue: Optional[str] = None
    to_queue: Optional[str] = None

class QueueMessage(BaseModel):
    """Model for messages passing through internal queues"""
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    processing_path: List[ProcessingPathEntry] = Field(default_factory=list)
    forwarding_path: List[ForwardingPathEntry] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp()
        }

# --- BaseMessage and derivatives ---
# Keeping these as they are, but reiterating that WebSocketMessage is key for comms.
class BaseMessage(BaseModel):
    type: str
    timestamp: float = Field(default_factory=time.time)
    status: str = "pending"
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

# --- This is your primary WebSocket Message Model ---
class WebSocketMessage(BaseModel):
    # <--- ADD THIS FIELD TO YOUR WebSocketMessage MODEL!
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
    
    # Message routing and processing tracking
    processing_path: List[str] = Field(
        default_factory=list,
        description="Tracking of processing steps (e.g. ['message_processor', 'queue_forwarder'])"
    )
    forwarding_path: List[str] = Field(
        default_factory=list,
        description="Tracking of queue forwarding steps (e.g. ['from_frontend', 'to_backend'])"
    )
    _trace: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Internal tracing metadata",
        exclude=True  # Don't include in dict() by default
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp()
        }
        schema_extra = {
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
