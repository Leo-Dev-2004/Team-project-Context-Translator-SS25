# Backend Tests

This directory contains all backend tests for the Context Translator project.

## Running Tests

Use the comprehensive test runner:

```bash
# Run all tests
python Backend/run_backend_tests.py

# Run with verbose output
python Backend/run_backend_tests.py --verbose

# Run a specific test
python Backend/run_backend_tests.py --test test_settings_manager

# Save results to JSON
python Backend/run_backend_tests.py --output results.json

# Set custom timeout (default: 15s)
python Backend/run_backend_tests.py --timeout 30
```

## Test Status

The test runner returns sentinel values for each test:
- **OK**: Test passed successfully
- **WARNING**: Test completed but had warnings or minor issues
- **ERROR**: Test failed or timed out

## Test Coverage

### Tested Modules
- ✓ Backend/AI/MainModel.py
- ✓ Backend/AI/SmallModel.py
- ✓ Backend/core/settings_manager.py
- ✓ Backend/services/ExplanationDeliveryService.py
- ✓ Backend/MessageRouter.py
- ✓ Backend/backend.py
- ✓ Backend/STT/transcribe.py

### Untested Modules (Need Tests)
- ✗ Backend/core/session_manager.py
- ✗ Backend/core/Queues.py
- ✗ Backend/services/WebSocketManager.py
- ✗ Backend/queues/MessageQueue.py
- ✗ Backend/queues/QueueTypes.py
- ✗ Backend/api/endpoints.py
- ✗ Backend/models/UniversalMessage.py
- ✗ Backend/dependencies.py

## Disabled Tests

The following tests are currently disabled (renamed to `.disabled`) due to business logic issues or bugs:

1. **test_adaptive_filtering.py.disabled** - Adaptive threshold logic has 2 assertion failures
2. **test_confidence_filter.py.disabled** - Confidence filtering logic has 1 assertion failure  
3. **test_hallucination_filtering.py.disabled** - SmallModel hallucination filtering has 4 failures
4. **test_hallucination_final_verification.py.disabled** - Legitimate content preservation failures
5. **test_stt_heartbeat_websocket_state.py.disabled** - Code bug: `websockets.exceptions` doesn't exist

These tests should be:
- Reviewed for correctness
- Fixed if the business logic is wrong
- Updated if the test expectations are wrong
- Re-enabled once issues are resolved

## Test Organization

Tests are organized by the module they test:

### AI Tests
- `test_mainmodel*.py` - MainModel functionality
- `test_smallmodel.py` - SmallModel functionality
- `test_full_pipeline.py` - Complete SmallModel → MainModel pipeline

### Settings Tests
- `test_settings_manager.py` - Settings management
- `test_settings_integration.py` - Settings integration
- `test_complete_implementation.py` - Complete settings implementation

### Integration Tests
- `test_backend_lifecycle.py` - Backend startup/shutdown
- `test_integration_simple.py` - Simple integration test
- `test_explanation_delivery_events.py` - Explanation delivery service

### Message Routing Tests
- `test_manual_request.py` - Manual request handling
- `test_manual_request_confidence.py` - Confidence scoring

### Other Tests
- `test_qwen_simple.py` - Qwen3 API call testing
- `test_latency_demonstration.py` - Latency testing
- `test_option_b_integration.py` - Event-driven integration

## Adding New Tests

When adding new tests:

1. Follow the naming convention: `test_<module_name>.py`
2. Use the standard import pattern:
   ```python
   from pathlib import Path
   import sys
   
   # Add project root to Python path for imports
   project_root = Path(__file__).parent.parent.parent
   sys.path.insert(0, str(project_root))
   
   from Backend.module_name import ModuleName
   ```
3. Make tests runnable both standalone and via the test runner
4. Add clear assertions and error messages
5. Update this README with the new test

## GitHub Issues for Untested Modules

See the following GitHub issues for implementing tests for untested modules:
- (Issues to be created)
