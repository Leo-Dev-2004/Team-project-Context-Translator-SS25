from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any # Added Any for Dict values
from datetime import datetime
import time

class QueueMessage(BaseModel):
    """Model for messages passing through internal queues"""
    type: str
    data: Dict[str, Any] = Field(default_factory=dict) # Explicitly use Field for dict default
    timestamp: float = Field(default_factory=time.time)
    processing_path: List[Dict[str, Any]] = Field(default_factory=list) # Ensure list is mutable default
    forwarding_path: List[Dict[str, Any]] = Field(default_factory=list) # Ensure list is mutable default
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp()
        }

# --- BaseMessage and derivatives are a bit unusual for WebSockets
# --- Often, WebSocketMessage handles the 'type' and 'data' directly
# --- I'm keeping them for now, but consider if they're strictly needed
# --- or if WebSocketMessage can be the primary message model for all comms.
class BaseMessage(BaseModel):
    type: str
    timestamp: float = Field(default_factory=time.time) # Use Field for mutable default
    status: str = "pending" # Default here is fine as it's immutable
    processing_path: List[Dict[str, Any]] = Field(default_factory=list) # Ensure mutable default
    forwarding_path: List[Dict[str, Any]] = Field(default_factory=list) # Ensure mutable default

class SystemMessage(BaseMessage):
    data: Dict[str, Any] # Changed from str to Any to match common usage

class SimulationMessage(BaseMessage):
    data: Dict[str, Any] # Changed from str to Any

class FrontendMessage(BaseMessage):
    data: Dict[str, Any] # Changed from str to Any

class BackendProcessedMessage(BaseMessage):
    data: Dict[str, Any] # Changed from str to Any
    progress: Optional[int] = None

# --- This is your primary WebSocket Message Model ---
class WebSocketMessage(BaseModel):
    type: str = Field(
        ...,
        description="Message type is required (e.g. 'command', 'data', 'status')",
        examples=["command", "data", "status"] # Changed 'example' to 'examples' for list, safer
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Message payload data",
        examples=[{"command": "start_simulation"}, {"message": "Hello"}] # Changed 'example' to 'examples' for list
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp of message creation"
    )
    client_id: Optional[str] = Field(
        None,
        description="Optional client identifier",
        examples=["client_123", "another_client_id"] # Changed 'example' to 'examples' for list
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp()
        }
        schema_extra = {
            "examples": [ # Use 'examples' for the list of model examples
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