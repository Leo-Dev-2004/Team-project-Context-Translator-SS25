from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import time

class QueueMessage(BaseModel):
    """Model for messages passing through internal queues"""
    type: str
    data: Dict[str, Any] = {}  # Default empty dict to ensure field exists
    timestamp: float = Field(default_factory=time.time)
    processing_path: List[Dict[str, Any]] = Field(default_factory=list)
    forwarding_path: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp()
        }

class BaseMessage(BaseModel):
    type: str
    timestamp: float = time.time()
    status: str = "pending"
    processing_path: List[Dict] = []
    forwarding_path: List[Dict] = []

class SystemMessage(BaseMessage):
    data: Dict[str, str]

class SimulationMessage(BaseMessage):
    data: Dict[str, str]

class FrontendMessage(BaseMessage):
    data: Dict[str, str]

class BackendProcessedMessage(BaseMessage):
    data: Dict[str, str]
    progress: Optional[int] = None

class WebSocketMessage(BaseModel):
    type: str = Field(..., description="Message type is required")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    client_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.timestamp()
        }
