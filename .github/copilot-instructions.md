# AI Coding Agent Instructions (Frontend Focus)

Concise, project-specific guidance for automated changes. Keep edits minimal, preserve behavior, prefer deletion of dead code over refactors.

## Big Picture
- Product: Desktop-only (Electron) real-time meeting assistant producing AI "explanations". (Former web build path has been discontinued; `packages/web` is deprecated and can be removed.) Backend (FastAPI/WebSocket :8000) <-> Electron renderer via structured JSON messages.
- Frontend code now centers on two active areas: `packages/shared` (core logic + Lit UI + queues) and `packages/electron` (Electron main/preload/renderer glue). Eliminate assumptions of a browser/PWA build.
- Core domain objects: UniversalMessage (backend JSON) → parsed by `UniversalMessageParser` → stored in singleton `ExplanationManager` → rendered as `<explanation-item>` within `<my-element>` (base class `UI`, subclassed in Electron).
- Messaging pipeline: queues abstract async flow: outbound (`toBackendQueue`) + inbound (`fromBackendQueue`) plus internal display/action queues. `WebSocketManager` bridges queues <-> WebSocket; `MessagingService` (partially unused) provides ping + high-level send. Legacy direct WebSocket in `electron/src/renderer.js` still duplicates session logic (target for consolidation).

## Runtime Flows
1. Electron startup: `electron/src/main.js` creates window, preload exposes `electronAPI` (settings, version, user session id).
2. Renderer loads `renderer.js` which imports `shared/src/index.js` (barrel) and calls `initializeApplication(this)` from `shared/app.js` inside `firstUpdated()`.
3. `app.js` sets up queues, assigns UI component to `WebSocketManager`, wires event listeners (`EventListeners.js`), starts WebSocket.
4. `WebSocketManager` maintains connection, enqueues incoming messages, dequeues outbound loop. Queue size UI updates via `QueueDisplay.js` (shadowRoot lookups).
5. `EventListeners.js` consumes `frontendDisplayQueue` in a loop, routes message types to UI/log updates.
6. Explanation messages (future) should be parsed -> `ExplanationManager.addExplanation()` then Lit re-renders.

## Key Modules & Responsibilities
- `shared/src/ui.js`: Base Lit component (tabs, session buttons, explanation list). Child overrides session actions.
- `shared/src/explanation-manager.js`: Singleton store + sorting/pinning + sessionStorage persistence.
- `shared/src/explanation-item.js`: Individual explanation card (expand, pin, delete, copy).
- `shared/src/universal-message-parser.js`: Heuristics mapping heterogeneous backend messages into explanation items.
- `shared/src/modules/MessageQueue.js`: Async blocking queue with listener subscription (dequeue waits via promise + wakes on enqueue).
- `shared/src/modules/WebSocketManager.js`: Connection lifecycle, reconnection, queue bridging, UI update hooks (direct DOM shadow queries) + sends initial `frontend.ready_ack`.
- `shared/src/modules/MessagingService.js`: High-level send + ping loop. (Currently unused in Electron renderer’s direct WebSocket path.)
- `shared/src/modules/EventListeners.js`: Attaches button handlers (translation, simulation), processes display queue messages (state machine for UI logs & statuses).
- `shared/src/modules/QueueDisplay.js`: Indirection layer to update shadow DOM safely after component mount.
- `electron/src/renderer.js`: Electron-specific subclass, duplicates some WebSocket/session logic outside queue system (candidate for consolidation).

## Current Duplication / Cleanup Targets
1. Dual WebSocket paths: remove manual WebSocket in `renderer.js`; migrate session start/join into queue-driven messaging.
2. Session management: unify into queue/event pipeline (`MessagingService.sendToBackend('session.start'| 'session.join')`).
3. Empty placeholder: `packages/shared/index.js` — remove or re-export barrel of `src/index.js`.
4. Remove dead listener code in `EventListeners.js` referencing non-existent IDs (translation/simulation artifacts).
5. Deprecate/delete `packages/web` folder (no longer shipped). Ensure docs / scripts have no references.
6. Keep CSS centralized (`styles.js` + `index.css`).

## Conventions
- Use ES modules in shared package (`type": "module"`); Electron preload uses CommonJS intentionally.
- Message shape: `{ id, type, timestamp (sec or ms), payload, client_id, origin, destination }`; queues may augment with `status`.
- Explanation ordering: pinned first (recent pinned first), then unpinned newest-first.
- Shadow DOM access must go through component reference; avoid direct global `document.getElementById` in shared modules (migrate remaining occurrences).

## Safe Operation Guidelines for Agents
- Prefer removal of clearly dead code over partial rewrites (e.g., if an element ID is never rendered in `ui.js`, remove its handler & references).
- When touching WebSocket logic, keep queue contract: outbound = `toBackendQueue`, inbound = `fromBackendQueue`; never block main thread—use existing async dequeue loop.
- Don’t introduce new framework layers; stay with Lit + existing singleton patterns.
- Keep preload surface minimal; no direct exposing of fs APIs beyond existing settings pattern.
- If adding new message types, extend switch in `EventListeners.processFrontendDisplayQueueMessages` and (optionally) parser mapping.

## Typical Commands (Electron Only)
- Development: from `Frontend/packages/electron`: `npm install` (first time) then `npm run dev` (Vite + Electron)
- (Optional) Build (when implemented): `npm run build` inside `packages/electron` (replace "..." placeholders before relying on CI)
- Remove any references to `dev:web` or `build:web` in higher-level docs/scripts.

## Integration Points
- Backend WebSocket: ws://localhost:8000/ws/{client_id}
- Simulation REST (if still supported): POST http://localhost:8000/simulation/{start|stop}
- Settings persistence: Electron main writes JSON to user home (`~/.context-translator-settings.json`). (Browser storage fallback dropped with web removal.)

## Prioritized Cleanup Suggestions (Electron-Only)
1. Remove legacy WebSocket + session code from `renderer.js`; replace with queue-backed calls.
2. Wire explanation parsing: in display queue loop, detect explanation messages → `UniversalMessageParser.parseAndAddToManager`.
3. Delete `packages/web` (or keep temporarily with CLEAR `DEPRECATED.md`).
4. Prune unused DOM ID handlers in `EventListeners.js` & any simulation/translation UI not rendered.
5. Replace empty `packages/shared/index.js` with proper re-export or delete.
6. Add message type registry doc (list type → handler module) to README.

## When Adding Files
- Place shared logic under `packages/shared/src/...`; Electron-only wrappers in `packages/electron/src`.
- Export new shared modules via `shared/src/index.js` barrel.
- Maintain German copy consistency where already used (e.g., session buttons).

## Non-Goals
- Do not resurrect web build path without architectural review.
- No TypeScript introduction unless explicitly requested.
- Avoid broad refactors of queues/WebSocket unless fixing concrete bugs.
- Don’t rewrite Lit components into React/Vue.

## Example: Adding a New Explanation Message Type
1. Backend emits `explanation.term` with payload `{ term, definition }`.
2. `EventListeners` display loop sees message, calls `UniversalMessageParser.parseAndAddToManager(message, explanationManager)` if `isExplanationMessage`.
3. UI auto-updates through listener binding.

Keep changes surgical, documented in PR description, and update `README.md` if build or run workflow changes.
