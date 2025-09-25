# Component Diagram: Electron & Backend Modules

## Why this diagram style?
A component diagram is ideal for visualizing the major building blocks of a modular, scalable system. It shows how Electron frontend modules, shared UI, backend services, and file-based queues interact, making architectural boundaries and interfaces explicit.

## Rationale for chosen components
- **Electron App (main, preload, renderer):** Separates process lifecycle, secure IPC, and UI logic for desktop integration and security.
- **Shared UI Modules:** Centralizes explanation management and UI components for reusability and maintainability.
- **Backend Services (WebSocketManager, MessageRouter, ExplanationDeliveryService, MainModel, SmallModel):** Each service is single-responsibility, enabling independent scaling and clear separation of concerns.
- **File Queues & Cache:** Decouples detection and explanation flows, allowing atomic writes and resilience to slow AI operations.

## How these components enable scalability, modularity, and decoupling
- **Scalability:** Services and models can be scaled independently (e.g., run multiple MainModel instances, separate STT process).
- **Modularity:** Each module (Electron, backend, UI, queues) is self-contained and can be updated or replaced without affecting others.
- **Decoupling:** File-based queues and explicit interfaces (IPC, WebSocket) ensure that slow or failing components do not block the rest of the system. This supports robust error handling and future extensibility.

## Render instructions
To re-render the diagram:
```zsh
./scripts/render-diagram.sh diagrams/architecture-components.mermaid
```
Artifacts will be placed in this folder for discoverability and archiving.