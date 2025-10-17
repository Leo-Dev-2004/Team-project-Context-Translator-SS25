#!/usr/bin/env python3
"""
Test to verify that manual requests get proper confidence scores.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch, AsyncMock

import pytest

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from Backend.MessageRouter import MessageRouter
from Backend.models.UniversalMessage import UniversalMessage
from Backend.core.Queues import queues


@pytest.mark.asyncio
async def test_manual_request_gets_confidence_score(tmp_path: Path, monkeypatch):
    """Test that manual requests receive confidence scores from AI detection."""
    # Arrange: point SmallModel to a temporary detections file
    detections_file = tmp_path / "detections_queue.json"

    router = MessageRouter()

    # Monkeypatch SmallModel's detections file path
    router._small_model.detections_queue_file = detections_file

    # Ensure router is in running state for consistency
    router._running = True

    # Mock AI detection to return a specific confidence score for the requested term
    mock_ai_terms = [{
        "term": "OAuth",
        "confidence": 0.85,
        "context": "OAuth authentication",
        "timestamp": int(time.time())
    }]
    
    # Mock the detect_terms_with_ai method to return our controlled result
    with patch.object(router._small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=mock_ai_terms)):
        # Build a manual.request message
        msg = UniversalMessage(
            type='manual.request',
            payload={'term': 'OAuth', 'context': 'OAuth authentication'},
            origin='test',
            destination=None,
            client_id=f'frontend_renderer_{uuid4()}'
        )

        # Act: process the client message
        await router._process_client_message(msg)

        # Assert: the detections file exists and contains our entry with confidence
        assert detections_file.exists(), "Detections file should be created"
        data = json.loads(detections_file.read_text(encoding='utf-8'))
        assert isinstance(data, list) and len(data) >= 1
        
        last = data[-1]
        assert last["term"] == 'OAuth'
        assert last["context"] == 'OAuth authentication'
        assert last["status"] == 'pending'
        assert last["client_id"] == msg.client_id
        assert last.get("timestamp") is not None
        assert last.get("confidence") == 0.85  # Should match the mocked AI response


@pytest.mark.asyncio
async def test_manual_request_default_confidence_when_term_not_found(tmp_path: Path, monkeypatch):
    """Test that manual requests get default confidence when AI doesn't find the exact term."""
    # Arrange: point SmallModel to a temporary detections file
    detections_file = tmp_path / "detections_queue.json"

    router = MessageRouter()
    router._small_model.detections_queue_file = detections_file
    router._running = True

    # Mock AI detection to return different terms (not matching requested term)
    mock_ai_terms = [{
        "term": "SomeOtherTerm",
        "confidence": 0.95,
        "context": "CustomTerm context",
        "timestamp": int(time.time())
    }]
    
    with patch.object(router._small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=mock_ai_terms)):
        # Build a manual.request message for a term not found by AI
        msg = UniversalMessage(
            type='manual.request',
            payload={'term': 'CustomTerm', 'context': 'CustomTerm context'},
            origin='test',
            destination=None,
            client_id=f'frontend_renderer_{uuid4()}'
        )

        # Act: process the client message
        await router._process_client_message(msg)

        # Assert: should get default confidence of 0.7
        assert detections_file.exists(), "Detections file should be created"
        data = json.loads(detections_file.read_text(encoding='utf-8'))
        assert isinstance(data, list) and len(data) >= 1
        
        last = data[-1]
        assert last["term"] == 'CustomTerm'
        assert last.get("confidence") == 0.7  # Should use default confidence


@pytest.mark.asyncio
async def test_manual_request_confidence_fallback_on_ai_failure(tmp_path: Path, monkeypatch):
    """Test that manual requests get default confidence when AI detection fails."""
    # Arrange: point SmallModel to a temporary detections file
    detections_file = tmp_path / "detections_queue.json"

    router = MessageRouter()
    router._small_model.detections_queue_file = detections_file
    router._running = True

    # Mock AI detection to return empty list (AI failure case)
    with patch.object(router._small_model, 'detect_terms_with_ai', new=AsyncMock(return_value=[])):
        # Build a manual.request message
        msg = UniversalMessage(
            type='manual.request',
            payload={'term': 'FailTerm', 'context': 'FailTerm context'},
            origin='test',
            destination=None,
            client_id=f'frontend_renderer_{uuid4()}'
        )

        # Act: process the client message
        await router._process_client_message(msg)

        # Assert: should get default confidence of 0.7
        assert detections_file.exists(), "Detections file should be created"
        data = json.loads(detections_file.read_text(encoding='utf-8'))
        assert isinstance(data, list) and len(data) >= 1
        
        last = data[-1]
        assert last["term"] == 'FailTerm'
        assert last.get("confidence") == 0.7  # Should use default confidence