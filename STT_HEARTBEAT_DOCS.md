# STT Heartbeat Feature Documentation

## Overview
This document describes the heartbeat mechanism implemented in the STT (Speech-to-Text) service to prevent WebSocket connection timeouts during periods of silence.

## Problem Addressed
The STT service was experiencing connection drops during extended periods of silence because:
- No messages were sent to the backend when no speech was detected
- WebSocket connections would timeout due to inactivity
- This resulted in interruptions to the transcription service

## Solution
A heartbeat mechanism that sends periodic keep-alive messages during silence periods.

## Implementation Details

### Configuration
Located in `Backend/STT/transcribe.py` - `Config` class:
```python
HEARTBEAT_INTERVAL_S = 30.0  # Send heartbeat every 30 seconds during silence
```

### Core Components

#### 1. Heartbeat Message Format
```json
{
  "id": "unique-uuid",
  "type": "stt.heartbeat",
  "timestamp": 1234567890.123,
  "payload": {
    "message": "keep-alive",
    "user_session_id": "session_id"
  },
  "origin": "stt_module",
  "client_id": "stt_instance_uuid"
}
```

#### 2. STTService Methods
- **`_send_heartbeat(websocket)`**: Sends heartbeat message to backend
- **Modified `_process_audio_loop(websocket)`**: Integrated heartbeat timing logic

#### 3. Timing Logic
Heartbeats are sent when BOTH conditions are met:
- Time since last heartbeat ≥ `HEARTBEAT_INTERVAL_S`
- Time since last activity ≥ `HEARTBEAT_INTERVAL_S`

This prevents unnecessary heartbeats when actual transcription activity is occurring.

#### 4. Backend Support
Modified `Backend/MessageRouter.py` to handle `stt.heartbeat` messages:
```python
elif message.type == 'stt.heartbeat':
    logger.debug(f"MessageRouter: Received heartbeat from STT client {message.client_id}")
    response = self._create_ack_message(message, "Heartbeat acknowledged.")
```

### Activity Tracking
The system tracks two timestamps:
- **`last_heartbeat_time`**: When the last heartbeat was sent
- **`last_activity_time`**: When the last significant activity occurred (speech detection, transcription sending)

### Error Handling
- Connection failures during heartbeat sending are logged but don't crash the service
- Heartbeat failures fall back to standard connection retry mechanisms

## Benefits
1. **Connection Stability**: Prevents timeout-based disconnections
2. **Efficient**: Only sends heartbeats during actual silence periods
3. **Non-intrusive**: Doesn't interfere with normal transcription operations
4. **Configurable**: Heartbeat interval can be adjusted via configuration

## Usage
The heartbeat mechanism is automatic and requires no changes to existing STT service usage:
```python
stt_service = STTService(user_session_id="your_session")
await stt_service.run()  # Heartbeats are handled automatically
```

## Testing
The implementation includes comprehensive tests:
- Message format validation
- Timing logic verification
- Connection failure handling
- Backend integration testing

## Configuration Recommendations
- **Production**: 30-60 seconds (current default: 30s)
- **Development**: 10-30 seconds for faster testing
- **Heavy Load**: Consider 60-120 seconds to reduce overhead

## Monitoring
Heartbeat activity is logged at DEBUG level:
```
Sent heartbeat keep-alive message
MessageRouter: Received heartbeat from STT client stt_instance_xyz
```

## Future Enhancements
- Adaptive heartbeat intervals based on connection stability
- Heartbeat response timeout detection
- Metrics collection for connection health monitoring