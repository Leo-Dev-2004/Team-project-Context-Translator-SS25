from pydantic import BaseModel
from typing import Optional, List, Dict
import time

class QueueMessage(BaseModel):
    """Model for messages passing through internal queues"""
    type: str
    data: Dict[str, Any]
    timestamp: float = time.time()
    processing_path: List[Dict[str, Any]] = []
    forwarding_path: List[Dict[str, Any]] = []
    
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

class WebSocketMessage(BaseMessage):
    client_id: Optional[str] = None
