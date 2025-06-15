## ⚠️ Disclaimer

This README is intended **only for developers** working on the **Web App** and **Electron Desktop App** components of the project. It focuses exclusively on the development, structure, and usage of these two modules within the monorepo.

Other modules, such as backend services (e.g., WebSocket servers, APIs, etc.), are **not covered** in this guide. Please refer to their respective documentation for details on setup

# Context Translator

Real-time meeting translation powered by AI - Available as Web App and Desktop Application.

## 🚀 Quick Start

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd my-lit-app
   ```

2. Install all dependencies for the monorepo:
   ```bash
   npm install
   ```

### Development

The project uses a **monorepo structure** with three main packages:

- **`packages/shared/`**: Shared components and styles (Lit components, Material Design styles).
- **`packages/web/`**: Web version of the app (browser-based).
- **`packages/electron/`**: Desktop version of the app (Electron-based).

#### Run the Web App (Browser)
```bash
npm run dev:web
```
- Opens the web app at [http://localhost:5173](http://localhost:5173).

#### Run the Desktop App (Electron)
```bash
npm run dev:electron
```
- Opens the Electron desktop app.

### Building

#### Build the Web App
```bash
npm run build:web
```
- Outputs the production build to `packages/web/dist`.

#### Build the Desktop App
```bash
npm run build:electron
```
- Outputs the production build to `packages/electron/dist-electron`.

#### Build Everything
```bash
npm run build:all
```
- Builds both the web and desktop apps.

### Cleaning Build Artifacts
To clean all build outputs:
```bash
npm run clean
```

## 📁 Project Structure

```
my-lit-app/
├── packages/
│   ├── shared/       # Shared Lit components and styles
│   ├── web/          # Web app (browser-based)
│   └── electron/     # Desktop app (Electron-based)
├── public/           # Public assets (shared across apps)
├── package.json      # Monorepo configuration and scripts
└── README.md         # Project documentation
```

### Packages Overview

#### `packages/shared/`
- Contains reusable Lit components and Material Design styles.
- Example components:
  - `MyElement`: The main app component.
- Example styles:
  - `index.css`: Shared CSS variables and global styles.

#### `packages/web/`
- Web app implementation.
- Uses `localStorage` for settings and supports Google Meet integration.

#### `packages/electron/`
- Desktop app implementation.
- Uses Electron APIs for native features like file dialogs and persistent settings storage.

## 🛠️ Development Commands

| Command                | Description                                      |
|------------------------|--------------------------------------------------|
| `npm run dev:web`      | Start the web app in development mode.           |
| `npm run dev:electron` | Start the desktop app in development mode.       |
| `npm run build:web`    | Build the web app for production.                |
| `npm run build:electron` | Build the desktop app for production.          |
| `npm run build:all`    | Build both the web and desktop apps.             |
| `npm run clean`        | Clean all build outputs.                         |

## 🌟 Features

### Web Version
- Google Meet Add-on Integration.
- Browser `localStorage` for settings.
- Progressive Web App (PWA) ready.
- Responsive design.

### Desktop Version
- Persistent settings storage in the file system.
- Native file dialogs for import/export.
- System menu integration.
- Offline functionality.
- Auto-updater ready.

## 🔧 Tech Stack

- **Frontend**: Lit + Material Web Components.
- **Build Tool**: Vite.
- **Desktop**: Electron.
- **Package Management**: npm workspaces.
- **Styling**: Material Design 3.

## 🎯 Getting Started

1. **Install dependencies**: `npm install`.
2. **Start development**: Choose `npm run dev:web` or `npm run dev:electron`.
3. **Configure settings**: Use the "Settings" tab in the app to set your preferences.
4. **Start translating**: Switch to the "Translator" tab and begin!

Both versions share the same UI and core functionality, with platform-specific enhancements.