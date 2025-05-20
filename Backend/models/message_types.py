from pydantic import BaseModel
from typing import Optional, List, Dict
import time

class QueueMessage(BaseModel):
    type: str
    data: dict
    timestamp: float = time.time()
    status: str = "pending"
    processing_path: List[Dict] = []
    forwarding_path: List[Dict] = []

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
