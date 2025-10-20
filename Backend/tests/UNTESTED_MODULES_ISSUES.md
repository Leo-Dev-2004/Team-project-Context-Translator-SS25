# GitHub Issues for Untested Backend Modules

This document contains issue templates for implementing tests for currently untested Backend modules.

---

## Issue 1: Add tests for Backend/core/session_manager.py

**Title:** Add comprehensive tests for SessionManager

**Description:**

The `SessionManager` class in `Backend/core/session_manager.py` currently has no test coverage. This module manages session creation and joining functionality.

### Module Overview
- **File:** `Backend/core/session_manager.py`
- **Purpose:** Manages active sessions with unique codes and participant tracking
- **Key Functions:**
  - `generate_session_code()` - Generates random session codes
  - `create_session()` - Creates new sessions
  - `join_session()` - Adds participants to sessions
  - `get_active_session_code()` - Returns active session code

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_session_manager.py`

2. **Test cases to implement:**
   - Test session creation with valid client ID
   - Test preventing multiple simultaneous sessions
   - Test joining session with correct code
   - Test joining session with incorrect code
   - Test session code generation (length, uniqueness)
   - Test participant tracking
   - Test getting active session code

3. **Test structure:**
   ```python
   from pathlib import Path
   import sys
   
   project_root = Path(__file__).parent.parent.parent
   sys.path.insert(0, str(project_root))
   
   from Backend.core.session_manager import SessionManager, generate_session_code
   
   def test_session_creation():
       manager = SessionManager()
       code = manager.create_session("client1")
       assert code is not None
       assert len(code) == 6
       # Return OK
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

5. **GitHub Actions integration:**
   - Add to existing test workflow or create new one
   - Ensure test runs on PR and push events

---

## Issue 2: Add tests for Backend/core/Queues.py

**Title:** Add tests for global Queues singleton

**Description:**

The `Queues` singleton class in `Backend/core/Queues.py` manages all global message queues but has no test coverage.

### Module Overview
- **File:** `Backend/core/Queues.py`
- **Purpose:** Singleton pattern for managing global message queues
- **Key Features:**
  - Manages incoming, outgoing, and websocket_out queues
  - Singleton pattern implementation
  - Queue retrieval methods

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_queues.py`

2. **Test cases to implement:**
   - Test singleton pattern (multiple instances return same object)
   - Test initialization creates all queues
   - Test get_all_queues returns correct structure
   - Test queue types are correct (MessageQueue instances)

3. **Test structure:**
   ```python
   from pathlib import Path
   import sys
   
   project_root = Path(__file__).parent.parent.parent
   sys.path.insert(0, str(project_root))
   
   from Backend.core.Queues import Queues, queues
   
   def test_singleton_pattern():
       q1 = Queues()
       q2 = Queues()
       assert q1 is q2
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Issue 3: Add tests for Backend/services/WebSocketManager.py

**Title:** Add comprehensive tests for WebSocketManager

**Description:**

The `WebSocketManager` class in `Backend/services/WebSocketManager.py` handles WebSocket connections and message dispatching but lacks test coverage.

### Module Overview
- **File:** `Backend/services/WebSocketManager.py`
- **Purpose:** Manages WebSocket connections and message routing
- **Key Features:**
  - Connection management
  - Client task management
  - Message dispatching
  - Graceful shutdown

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_websocket_manager.py`

2. **Test cases to implement:**
   - Test connection registration
   - Test connection removal
   - Test message dispatching to clients
   - Test graceful shutdown
   - Test handling of disconnected clients
   - Test user session mapping

3. **Use mocking for WebSocket objects:**
   ```python
   from unittest.mock import AsyncMock, MagicMock
   import pytest
   
   @pytest.mark.asyncio
   async def test_connection_management():
       incoming_queue = AsyncMock()
       outgoing_queue = AsyncMock()
       manager = WebSocketManager(incoming_queue, outgoing_queue)
       
       mock_websocket = MagicMock()
       await manager.register_connection("client1", mock_websocket)
       
       assert "client1" in manager.connections
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Issue 4: Add tests for Backend/queues/MessageQueue.py

**Title:** Add tests for MessageQueue implementation

**Description:**

The `MessageQueue` class in `Backend/queues/MessageQueue.py` implements the queue functionality but has no dedicated tests.

### Module Overview
- **File:** `Backend/queues/MessageQueue.py`
- **Purpose:** Concrete implementation of AbstractMessageQueue
- **Key Features:**
  - Enqueue/dequeue operations
  - Queue snapshots
  - Message path tracking
  - Queue draining

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_message_queue.py`

2. **Test cases to implement:**
   - Test enqueue operation
   - Test dequeue operation
   - Test queue size tracking
   - Test get_items_snapshot
   - Test peek functionality
   - Test drain operation
   - Test message path tracking

3. **Test structure:**
   ```python
   import asyncio
   from Backend.queues.MessageQueue import MessageQueue
   from Backend.models.UniversalMessage import UniversalMessage
   
   async def test_enqueue_dequeue():
       queue = MessageQueue(name="test")
       msg = UniversalMessage(type="test", payload={}, client_id="c1")
       
       await queue.enqueue(msg)
       assert queue.qsize() == 1
       
       dequeued = await queue.dequeue()
       assert dequeued.type == "test"
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Issue 5: Add tests for Backend/queues/QueueTypes.py

**Title:** Add tests for AbstractMessageQueue interface

**Description:**

The `AbstractMessageQueue` in `Backend/queues/QueueTypes.py` defines the queue interface but has no tests verifying contract compliance.

### Module Overview
- **File:** `Backend/queues/QueueTypes.py`
- **Purpose:** Abstract base class for queue implementations
- **Key Features:**
  - Defines queue interface contract
  - Type hints for queue operations

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_queue_types.py`

2. **Test cases to implement:**
   - Test that MessageQueue implements all abstract methods
   - Test method signatures match interface
   - Test that concrete implementations satisfy ABC requirements

3. **Test structure:**
   ```python
   from Backend.queues.QueueTypes import AbstractMessageQueue
   from Backend.queues.MessageQueue import MessageQueue
   import inspect
   
   def test_message_queue_implements_interface():
       required_methods = ['enqueue', 'dequeue', 'qsize', 'get_items_snapshot', 'drain', 'peek']
       
       for method in required_methods:
           assert hasattr(MessageQueue, method)
       
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Issue 6: Add tests for Backend/api/endpoints.py

**Title:** Add integration tests for API endpoints

**Description:**

The FastAPI endpoints in `Backend/api/endpoints.py` need test coverage for all routes.

### Module Overview
- **File:** `Backend/api/endpoints.py`
- **Purpose:** FastAPI route definitions
- **Key Endpoints:**
  - GET / - Root endpoint
  - GET /health - Health check
  - GET /metrics - Metrics endpoint
  - GET /queues/debug - Queue debugging

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_api_endpoints.py`

2. **Test cases to implement:**
   - Test root endpoint returns welcome message
   - Test health check returns healthy status
   - Test metrics endpoint returns connection count
   - Test queue debug endpoint returns queue state

3. **Use FastAPI TestClient:**
   ```python
   from fastapi.testclient import TestClient
   from Backend.backend import app  # Assuming app is exported
   
   def test_health_endpoint():
       client = TestClient(app)
       response = client.get("/health")
       assert response.status_code == 200
       assert response.json()["status"] == "healthy"
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Issue 7: Add tests for Backend/models/UniversalMessage.py

**Title:** Add tests for UniversalMessage Pydantic model

**Description:**

The `UniversalMessage` Pydantic model in `Backend/models/UniversalMessage.py` is used throughout the system but has no direct tests.

### Module Overview
- **File:** `Backend/models/UniversalMessage.py`
- **Purpose:** Core message data structure
- **Key Features:**
  - Message validation
  - Timestamp generation
  - Processing path tracking
  - Model serialization/deserialization

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_universal_message.py`

2. **Test cases to implement:**
   - Test message creation with required fields
   - Test timestamp auto-generation
   - Test validation of required fields
   - Test model serialization (model_dump)
   - Test model deserialization (model_validate)
   - Test processing path tracking

3. **Test structure:**
   ```python
   from Backend.models.UniversalMessage import UniversalMessage
   
   def test_message_creation():
       msg = UniversalMessage(
           type="test.message",
           payload={"data": "value"},
           client_id="client123"
       )
       
       assert msg.type == "test.message"
       assert msg.payload["data"] == "value"
       assert msg.timestamp > 0
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Issue 8: Add tests for Backend/dependencies.py

**Title:** Add tests for dependency injection system

**Description:**

The dependency injection system in `Backend/dependencies.py` manages global instances but has no test coverage.

### Module Overview
- **File:** `Backend/dependencies.py`
- **Purpose:** Dependency injection for global services
- **Key Functions:**
  - Settings manager instance management
  - WebSocket manager instance management
  - Global instance getters/setters

### Test Implementation Workflow

1. **Create test file:** `Backend/tests/test_dependencies.py`

2. **Test cases to implement:**
   - Test setting and getting settings manager instance
   - Test setting and getting websocket manager instance
   - Test instance persistence
   - Test None handling when instances not set

3. **Test structure:**
   ```python
   from Backend.dependencies import (
       set_settings_manager_instance,
       get_settings_manager_instance
   )
   from Backend.core.settings_manager import SettingsManager
   
   def test_settings_manager_injection():
       manager = SettingsManager()
       set_settings_manager_instance(manager)
       
       retrieved = get_settings_manager_instance()
       assert retrieved is manager
       print("OK")
   ```

4. **Expected sentinel values:**
   - Return "OK" on successful test completion
   - Return "ERROR" on test failure

---

## Implementation Priority

Suggested order for implementation:

1. **High Priority:**
   - UniversalMessage.py (core data structure)
   - MessageQueue.py (core functionality)
   - session_manager.py (session handling)

2. **Medium Priority:**
   - WebSocketManager.py (connection management)
   - endpoints.py (API surface)
   - dependencies.py (DI system)

3. **Low Priority:**
   - Queues.py (simple singleton)
   - QueueTypes.py (interface validation)

## Automated Testing

All new tests should:
1. Follow the pattern established in existing tests
2. Be runnable via `Backend/run_backend_tests.py`
3. Return appropriate sentinel values (OK/WARNING/ERROR)
4. Include clear documentation
5. Be added to GitHub Actions workflow for CI/CD

## Notes

- Reference the Frontend test structure in `Frontend/src/components/status-bar.test.js` for test style
- Ensure all tests can run independently and as part of the test suite
- Use proper mocking for external dependencies
- Include both positive and negative test cases
- Add edge case testing where applicable
