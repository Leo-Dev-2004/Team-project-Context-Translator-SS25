import os
import sys

# Verify backend module location
backend_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Backend module located at: {backend_dir}")

from .backend import app
from .QueueManager.shared_queue import (
    MessageQueue,
    to_frontend_queue,
    from_frontend_queue,
    to_backend_queue,
    from_backend_queue
)

__all__ = [
    'app',
    'MessageQueue',
    'to_frontend_queue',
    'from_frontend_queue',
    'to_backend_queue',
    'from_backend_queue'
]
