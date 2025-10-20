import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from Backend.MessageRouter import MessageRouter
from Backend.models.UniversalMessage import UniversalMessage
from Backend.core.Queues import queues


@pytest.mark.asyncio
async def test_manual_request_writes_detection(tmp_path: Path, monkeypatch):
    # Arrange: point SmallModel to a temporary detections file
    detections_file = tmp_path / "detections_queue.json"

    router = MessageRouter()

    # Monkeypatch SmallModel's detections file path
    router._small_model.detections_queue_file = detections_file

    # Ensure router is in running state for consistency
    router._running = True

    # Build a manual.request message
    msg = UniversalMessage(
        type='manual.request',
        payload={'term': 'OAuth', 'context': 'Auth standard'},
        origin='test',
        destination=None,
        client_id=f'frontend_renderer_{uuid4()}'
    )

    # Act: process the client message
    await router._process_client_message(msg)

    # Assert: the detections file exists and contains our entry
    assert detections_file.exists(), "Detections file should be created"
    data = json.loads(detections_file.read_text(encoding='utf-8'))
    assert isinstance(data, list) and len(data) >= 1
    last = data[-1]
    assert last["term"] == 'OAuth'
    assert last["context"] == 'Auth standard'
    assert last["status"] == 'pending'
    assert last["client_id"] == msg.client_id
    assert last.get("timestamp") is not None
