# Network Architecture Diagram: Localhost & WebSocket Topology

## Rationale

This diagram models the network topology of the Context Translator, focusing on WebSocket connections, client IDs, CSP restrictions, and integration points. The technical version details all endpoints and client relationships for engineering and security review. The visual version is optimized for presentations, with color and simplified clusters.

## Diagram Versions

- **Technical:** Full endpoints, client IDs, and CSP details. Use for backend design, security, and integration.
- **Visual:** Simplified clusters, color-coded for clarity, suitable for onboarding and presentations.

## How This Topology Supports the Architecture

- Ensures secure, real-time communication via WebSocket and API endpoints.
- Supports multi-client scenarios and external integrations.
- CSP restricts connections for security and reliability.

## Render Instructions

To render the diagrams:

```sh
npx -y @mermaid-js/mermaid-cli -i technical/network-technical.mermaid -o technical/network-technical.svg
npx -y @mermaid-js/mermaid-cli -i visual/network-visual.mermaid -o visual/network-visual.svg
```

For PNG conversion:

```sh
rsvg-convert technical/network-technical.svg -o technical/network-technical.png
rsvg-convert visual/network-visual.svg -o visual/network-visual.png
```

## References

- See `CONTEXT.md` for connection details and security rationale.
- See backend code for WebSocketManager and CSP logic.
