# Context Translator Frontend

## Overview

Real-time meeting translation powered by AI - Available as Web App and Desktop Application.

The project uses a **2-way development path** with both web and desktop implementations sharing common components.

## 🚀 Getting Started

### Prerequisites
- Node.js (latest LTS version recommended)
- npm (comes with Node.js)
- Git for version control

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

### Quick Start Guide

1. **Install dependencies**: `npm install`
2. **Start development**: Choose `npm run dev:web` or `npm run dev:electron`
3. **Configure settings**: Use the "Settings" tab in the app to set your preferences
4. **Start translating**: Switch to the "Translator" tab and begin!

Both versions share the same UI and core functionality, with platform-specific enhancements.

## 🏗️ Project Architecture

### Monorepo Structure

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

### Package Details

#### `packages/shared/`
- Contains reusable Lit components and Material Design styles
- Example components:
  - `MyElement`: The main app component
- Example styles:
  - `index.css`: Shared CSS variables and global styles

#### `packages/web/`
- Web app implementation
- Uses `localStorage` for settings and supports Google Meet integration
- Progressive Web App (PWA) ready

#### `packages/electron/`
- Desktop app implementation
- Uses Electron APIs for native features like file dialogs and persistent settings storage
- Auto-updater ready

## 🛠️ Development Workflow

### Development Commands

| Command                | Description                                      |
|------------------------|--------------------------------------------------|
| `npm run dev:web`      | Start the web app in development mode           |
| `npm run dev:electron` | Start the desktop app in development mode       |
| `npm run build:web`    | Build the web app for production                |
| `npm run build:electron` | Build the desktop app for production          |
| `npm run build:all`    | Build both the web and desktop apps             |
| `npm run clean`        | Clean all build outputs                         |

### Development Modes

#### Run the Web App (Browser)
```bash
npm run dev:web
```
- Opens the web app at [http://localhost:5173](http://localhost:5173)

#### Run the Desktop App (Electron)
```bash
npm run dev:electron
```
- Opens the Electron desktop app

### Building for Production

#### Build the Web App
```bash
npm run build:web
```
- Outputs the production build to `packages/web/dist`

#### Build the Desktop App
```bash
npm run build:electron
```
- Outputs the production build to `packages/electron/dist-electron`

#### Build Everything
```bash
npm run build:all
```
- Builds both the web and desktop apps

### Cleaning Build Artifacts
To clean all build outputs:
```bash
npm run clean
```

## 🌟 Platform Features

### Web Version
- Google Meet Add-on Integration
- Browser `localStorage` for settings
- Progressive Web App (PWA) ready
- Responsive design
- Cross-platform compatibility

### Desktop Version
- Persistent settings storage in the file system
- Native file dialogs for import/export
- System menu integration
- Offline functionality
- Auto-updater ready
- Native OS notifications

## 📚 Documentation and Technologies

### Core Technology Stack

- **Frontend Framework**: Lit (lightweight web components)
- **Build Tool**: Vite (fast development and building)
- **Desktop Runtime**: Electron (cross-platform desktop apps)
- **Package Management**: npm workspaces (monorepo management)
- **Styling**: Material Design 3 (modern design system)

### Architecture References

- **Miro Board**: Detailed architecture diagrams (found at main README)

### Primary Documentation

#### Framework & Build Tools
- **Vite**: https://vite.dev/guide/ - Fast build tool with hot module replacement
- **npm**: https://docs.npmjs.com/getting-started/ - Package manager and workspace configuration
- **Node.js**: https://nodejs.org/en - JavaScript runtime environment
- **Lit Framework**: https://lit.dev/ - Simple, fast, web components library

#### UI Components & Design
- **Google Material Web Components**: https://material-web.dev/ - Note: Support paused, but still functional
- **Web Components Guide**: https://developer.mozilla.org/en-US/docs/Web/API/Web_components - Standard web component APIs
- **Material 3 Design System**: https://m3.material.io/develop/web - Modern design principles and guidelines

#### Google Meet Integration
- **Meet Add-Ons SDK Documentation**: https://developers.google.com/workspace/meet/add-ons/guides/overview - Complete integration guide
- **Meet Add-Ons SDK npm Package**: https://www.npmjs.com/package/@googleworkspace/meet-addons - Official SDK for development
- **Meet Add-Ons SDK Code Samples**: https://github.com/googleworkspace/meet/tree/main - Real-world implementation examples

#### Legacy APIs (No Longer Used)
- **Google Meet Media API**: https://developers.google.com/workspace/meet/media-api/guides/overview - Deprecated in favor of Add-Ons SDK

### Learning Resources

#### Web Development Fundamentals
- **MDN Web Docs**: https://developer.mozilla.org/en-US/docs/Learn_web_development - Comprehensive web development learning path
- **First Website Tutorial**: https://developer.mozilla.org/en-US/docs/Learn_web_development/Getting_started/Your_first_website/Creating_the_content
- **MDN Core Modules**: https://developer.mozilla.org/en-US/docs/Learn_web_development/Core - Essential web technologies
- **Google Fonts**: https://fonts.google.com/ - Typography resources

#### Command Line & Development Environment
- **Command Line Basics**: https://developer.mozilla.org/en-US/docs/Learn_web_development/Getting_started/Environment_setup/Command_line - Essential terminal skills

#### JavaScript & Package Management
- **Package Management Deep Dive**: https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Client-side_tools/Package_management#what_exactly_is_a_package_manager
- **MDN JavaScript Course**: https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting - Complete JS fundamentals
- **Node.js Documentation**: https://nodejs.org/en/ - Server-side JavaScript runtime

#### React (Alternative Framework Reference)
- **MDN React Tutorial**: https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Frameworks_libraries/React_getting_started
- **React Official Docs**: https://react.dev/ - Component-based UI library
- **React from Scratch**: https://react.dev/learn/build-a-react-app-from-scratch - Hands-on building guide
- **ESLint for React**: https://www.npmjs.com/package/eslint-config-react-app - Code quality and consistency tools

### Development Tools & Quality Assurance

- **Vite Build Tool**: https://vite.dev/guide/ - Modern build tooling with fast HMR
- **ESLint**: Code linting and style enforcement
- **Material Design**: Consistent UI/UX patterns
- **TypeScript**: Optional static typing (if implemented)