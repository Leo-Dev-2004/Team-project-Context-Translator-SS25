# Global Settings Management - Data Flow Analysis

## Overview
This document traces the complete data flow for the Global Settings Management implementation, documenting how settings flow from the Frontend through the Backend to the AI models.

## Current Implementation Status ✅

### 1. SettingsManager Service ✅
- **Location**: `Backend/core/settings_manager.py`
- **Features**: 
  - Centralized settings storage with default values
  - Update/retrieve settings via `update_settings()` and `get_setting()`
  - File persistence to `Backend/settings.json`
  - In-memory caching for performance

### 2. Dependency Integration ✅
- **Location**: `Backend/dependencies.py`
- **Implementation**: 
  - `set_settings_manager_instance()` / `get_settings_manager_instance()`
  - Global singleton pattern matching other services
  - Initialized in backend startup

### 3. Message Handler ✅
- **Location**: `Backend/MessageRouter.py` (lines 209-230)
- **Handler**: `settings.save` message type
- **Features**:
  - Accepts settings payload from Frontend
  - Updates SettingsManager
  - Optional file persistence
  - Returns acknowledgment or error response

### 4. Backend Integration ✅
- **Location**: `Backend/backend.py` (startup event)
- **Implementation**:
  - SettingsManager initialized during app startup
  - Settings loaded from file if available
  - Registered in dependency injection system

## Data Flow Diagram

```
Frontend (Electron)                Backend (FastAPI)                AI Models
─────────────────────            ─────────────────────            ──────────────

┌─────────────────────┐          ┌─────────────────────┐          ┌──────────────┐
│   UI Settings       │          │   MessageRouter     │          │  SmallModel  │
│   - Domain Input    │  WS      │   settings.save     │          │              │
│   - Style Selector  │ ──────→  │   Handler           │ ──────→  │  Uses domain │
│                     │          │                     │          │  from        │
│  _saveSettings()    │          │  SettingsManager    │          │  Settings-   │
│  (saves locally)    │          │  .update_settings() │          │  Manager     │
└─────────────────────┘          └─────────────────────┘          └──────────────┘
                                          │                        ┌──────────────┐
                                          │                        │  MainModel   │
                                          │                        │              │
                                          └─────────────────────── │  Uses domain │
                                                                   │  & style     │
                                                                   │  from        │
                                                                   │  Settings-   │
                                                                   │  Manager     │
                                                                   └──────────────┘
```

## Detailed Data Flow Steps

### Step 1: Frontend Settings Update
1. User changes domain/explanation style in UI
2. `renderer.js._saveSettings()` called
3. Settings saved locally via Electron IPC to `~/.context-translator-settings.json`
4. **NEEDS IMPLEMENTATION**: Frontend sends `settings.save` WebSocket message to Backend

### Step 2: Backend Message Processing
1. WebSocket message received by `MessageRouter` ✅
2. `settings.save` handler processes message payload ✅
3. Calls `SettingsManager.update_settings(payload)` ✅
4. SettingsManager updates in-memory settings ✅
5. Settings persisted to `Backend/settings.json` ✅
6. Acknowledgment sent back to Frontend ✅

### Step 3: AI Model Integration
1. **SmallModel** (`detect_terms_with_ai`): ✅
   - Checks `get_settings_manager_instance().get_setting("domain")`
   - Uses domain for contextual term detection
   
2. **MainModel** (`build_prompt`): ✅
   - Gets domain and explanation_style from SettingsManager
   - Incorporates into LLM prompts for better explanations

## Remaining Work 🔄

### Critical Missing Piece: Frontend WebSocket Integration
The only missing piece is updating the Frontend to send settings to the Backend via WebSocket.

**Current State**: Frontend only saves settings locally via Electron IPC
**Needed**: Also send settings.save message via WebSocket to Backend

### Location to Update
**File**: `Frontend/src/renderer.js`
**Method**: `_saveSettings()` (around line 410)

## Architecture Benefits

1. **Single Source of Truth**: SettingsManager centralizes all settings
2. **Loose Coupling**: Services request settings when needed (pull model)  
3. **Scalability**: Easy to add new settings and consumers
4. **Performance**: In-memory access for frequent operations
5. **Testability**: Clear separation of concerns
6. **Real-time Sync**: Frontend and Backend settings stay in sync
