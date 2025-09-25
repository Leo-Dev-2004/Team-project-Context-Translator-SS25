# Deployment Diagram: Visual & Technical Views

## Why two versions?
- **Visual (presentation):** Designed for clarity in presentations, using color, icons, and simplified labels to communicate the system's deployment at a glance.
- **Technical (engineering):** Includes explicit ports, process boundaries, and file paths for software architecture analysis, troubleshooting, and implementation.

## Why a deployment diagram?
Deployment diagrams show how software components are mapped to hardware/processes, network connections, and file locations. This is essential for understanding reliability, scalability, and operational boundaries.

## How deployment architecture supports reliability & scalability
- **Reliability:** File-based queues and atomic writes prevent data loss and corruption, even if processes crash or restart. Explicit process boundaries isolate failures.
- **Scalability:** Each process (Electron, STT, Backend) can be scaled independently. WebSocket and file-based communication decouple components, allowing horizontal scaling and future cloud migration.

## Render instructions
To render either version:
```zsh
./scripts/render-diagram.sh diagrams/architecture-deployment/visual/deployment-visual.mermaid
./scripts/render-diagram.sh diagrams/architecture-deployment/technical/deployment-technical.mermaid
```
Artifacts should be moved into their respective subdirectories for organization and archiving.
