# AI Coding Agent Instructions (Frontend)

Surgical, project-specific guidance for automated changes to the Electron Frontend. Keep edits minimal, preserve behavior, and favor deleting dead code over refactors.

## Big picture
- Product: Desktop-only Electron app showing real-time AI "explanations" from the backend over WebSocket (ws://localhost:8000).
- Frontend code lives entirely under `Frontend/` with:
	- `src/main.js` (Electron main)
	- `src/preload.js` (CommonJS, bundled to `dist-electron/preload.js`)
	- `src/renderer.js` (renderer entry and Electron-specific `<my-element>`)
	- `src/shared/*` (Lit UI, styles, explanation manager, parser)
- Core domain: UniversalMessage (backend JSON) → optional parsing by `UniversalMessageParser` → stored via `ExplanationManager` → rendered as `<explanation-item>` inside the base `UI` class (extended by the Electron renderer).

## Runtime flow
1. Main creates `BrowserWindow`, configures CSP, wires IPC (`get-app-version`, `get-platform`, settings read/write, `get-user-session-id`).
2. Preload exposes a minimal `window.electronAPI` (app info, dialogs, settings, user session id).
3. Renderer (`renderer.js`) defines and registers `<my-element>`, initializes Electron specifics, and opens a direct WebSocket to the backend.
4. UI (`ui.js`) renders tabs (Setup, Explanations), session controls, and the explanations list.
5. Explanations are managed in `explanation-manager.js` and rendered via `explanation-item.js` (Markdown with `marked`).

## Key modules
- `src/main.js`: window lifecycle, CSP for localhost:5174 and :8000, IPC handlers, app menu.
- `src/preload.js`: CommonJS bridge exposing safe APIs; bundled by esbuild to `dist-electron/preload.js`.
- `src/renderer.js`: Electron-specific subclass of `UI`, connects WebSocket, handles `session.start`/`session.join` and backend responses (`session.created`, `session.joined`, `session.error`).
- `src/shared/ui.js`: Base component with session UI; child should override `_startSession` and `_joinSession`.
- `src/shared/explanation-manager.js`: Singleton store, pinning, sorting, sessionStorage persistence.
- `src/shared/universal-message-parser.js`: Heuristics to convert incoming universal messages into explanation items.
- `src/shared/explanation-item.js`: Expand/collapse, pin, delete, copy; Markdown rendering with `marked`.
- `src/shared/styles.js` + `src/shared/index.css`: Style system.

## Conventions
- ES modules across the renderer and main; preload uses CommonJS by design.
- Message shape: `{ id, type, timestamp (sec or ms as number), payload, client_id, origin, destination }`.
- Explanation ordering: pinned first (most recent pinned first), then unpinned newest-first.
- Access UI through the component instance and `shadowRoot`; avoid global `document.getElementById` in shared modules.

## Safe operation guidelines
- Keep preload surface small; do not expose Node or fs directly beyond current handlers.
- When touching WebSocket logic, keep it non-blocking and on the renderer side; reuse the current `renderer.js` connection pattern.
- Prefer small additions over structural rewrites; do not introduce new frameworks.
- If enhancing explanation handling, consider `UniversalMessageParser.parseAndAddToManager(message, explanationManager)` when messages contain explanation data.

## Typical commands
- Development from `Frontend/`: `npm install` then `npm run dev` (starts Vite, builds preload in watch, launches Electron).
- Build: `npm run build` (renderer + preload + package via electron-builder `--dir`).
- Package/distribute: `npm run dist`.

## Integration points
- Backend WebSocket: `ws://localhost:8000/ws/{client_id}` (renderer).
- Settings persistence: JSON under the user home (handled by main process).
- CSP allows `localhost:5174` (dev) and `localhost:8000` for WebSocket/HTTP connections.

## Cleanup and improvement targets
1. Keep message parsing centralized: extend `renderer.js` to invoke `UniversalMessageParser` for explanation-like messages when the backend sends them.
2. Avoid duplicating session logic between UI and renderer; base UI methods should be overridden once in the Electron subclass.
3. Remove dead code paths or element IDs that aren’t rendered by `ui.js`.
4. Ensure all shared modules are exported via `src/shared/index.js` and imported from there in the renderer.

## When adding files
- Place renderer-visible, shared UI in `src/shared/` and export through `src/shared/index.js`.
- Electron-only integrations belong in `src/renderer.js` (renderer) or `src/main.js` (main). Update preload if new safe APIs are required.
- Keep German copy consistent where it already appears (e.g., session button labels).

## Non-goals
- Don’t add a web/PWA build without explicit approval.
- Don’t convert to TypeScript unless asked.
- Don’t replace Lit with other UI frameworks.

## Example: parsing an incoming explanation
1. Backend sends a universal message like `{ type: 'explanation.generated', payload: { title, content }, ... }`.
2. In `renderer.js` WebSocket `onmessage`, call `UniversalMessageParser.parseAndAddToManager(message, explanationManager)` if `UniversalMessageParser.isExplanationMessage(message)` is true.
3. The UI list updates automatically via the manager listener.

Document any behavior changes in PR descriptions and update `Frontend/README.md` if commands or run steps change.
