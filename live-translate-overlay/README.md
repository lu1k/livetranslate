# LiveTranslate Overlay

A minimal, performance-first live translation overlay — runs as a **standalone desktop app** via Electron, or directly in any browser.

---

## Project Structure

```
live-translate-overlay/
├── index.html                  # Frontend entry point
├── package.json                # npm scripts + electron-builder config
├── .gitignore
│
├── electron/
│   ├── main.js                 # Main process (window, tray, IPC, permissions)
│   ├── preload.js              # Secure IPC bridge (contextBridge)
│   ├── window-controls.js      # Drag bar + minimize/close buttons
│   └── assets/
│       └── README.txt          # Icon instructions
│
├── js/
│   ├── main.js                 # App boot + keyboard shortcuts
│   ├── router.js               # Hash-based router (lazy page loading)
│   └── pages/
│       ├── home.js             # Input selection page
│       └── sign.js             # Webcam / sign language page
│
└── styles/
    ├── base.css                # Variables, reset, shared components
    ├── home.css                # Home page styles
    └── sign.css                # Sign language page styles
```

---

## Prerequisites

- **Node.js** v18 or later — https://nodejs.org
- **npm** v9 or later (bundled with Node)

Verify:
```bash
node --version   # should print v18.x.x or higher
npm --version    # should print 9.x.x or higher
```

---

## Setup

```bash
# 1. Enter the project folder
cd live-translate-overlay

# 2. Install Electron and electron-builder
npm install
```

That's it. No bundler, no transpiler, no other dependencies.

---

## Running in Development

```bash
npm run dev
```

This opens the overlay window with DevTools detached so you can inspect and live-edit.

- The window is **frameless**, **transparent**, and **always-on-top** — exactly as it will appear in production.
- A slim drag bar appears at the top; grab it to reposition the overlay.
- **Right-click the tray icon** (system tray / menu bar) for opacity, always-on-top toggle, and quit.

### Global keyboard shortcut
**`Ctrl+Shift+T`** (Windows/Linux) or **`Cmd+Shift+T`** (macOS) — toggle show/hide from anywhere on your desktop, even when another app is focused.

### In-app shortcuts (when overlay is focused)
| Key | Action |
|---|---|
| `Space` | Start / Stop (context-aware) |
| `M` | Switch to Microphone input |
| `U` | Switch to URL input |
| `S` | Go to Sign Language mode |
| `Esc` | Return to Home |

---

## Running in the Browser (no Electron)

Open `preview.html` directly — no server or install needed:

```bash
# macOS
open preview.html

# Windows
start preview.html

# Linux
xdg-open preview.html
```

Or serve with any static server:
```bash
npx serve .
# then open http://localhost:3000
```

> Note: `preview.html` is a self-contained single-file version. `index.html` uses ES module imports and requires a server or Electron.

---

## Building a Distributable

### Windows (.exe installer)
```bash
npm run build:win
```

### macOS (.dmg)
```bash
npm run build:mac
```
> macOS builds must be run on a Mac. Code-signing requires an Apple Developer certificate for distribution outside your machine.

### Linux (.AppImage)
```bash
npm run build:linux
```

Built files are output to the `dist/` folder.

---

## Adding Icons (for production builds)

Place your icon files in `electron/assets/`:

| File | Format | Size | Used for |
|---|---|---|---|
| `tray-icon.png` | PNG | 16x16 or 32x32 | System tray |
| `icon.ico` | ICO | 256x256 | Windows app icon |
| `icon.icns` | ICNS | — | macOS app icon |
| `icon.png` | PNG | 512x512 | Linux app icon |

Free generator: **https://icon.kitchen** — upload one PNG, download all formats.

---

## Backend Integration Points

All backend hooks are marked with comments in the source:

### Translation service (`js/pages/home.js` — `handleStart()`)
Replace the `alert()` stub:
```js
import { TranslationService } from '../services/translation.js';

TranslationService.start({
  type: state.inputType,   // 'mic' | 'url'
  url:  state.url,
  from: state.sourceLang,
  to:   state.targetLang,
});
navigate('/translating');
```

### Sign language recognition (`js/pages/sign.js` — inside `setInterval`)
```js
const canvas = new OffscreenCanvas(640, 480);
canvas.getContext('2d').drawImage(video, 0, 0);
canvas.convertToBlob({ type: 'image/jpeg', quality: 0.7 })
  .then(blob => ws.send(blob));

ws.onmessage = ({ data }) => {
  recBox.textContent = JSON.parse(data).text;
};
```

---

## Performance Notes

| Decision | Why |
|---|---|
| Zero framework | No React/Vue runtime overhead (~0 KB vs 30-130 KB) |
| Hash router + `import()` | Pages parsed only when visited |
| Imperative DOM | No virtual DOM diffing; mutations are surgical |
| Listener registry + `unmount()` | All listeners removed on route change — no leaks |
| CSS-only animations | Run on compositor thread, no JS frame budget cost |
| 1 Hz stats `setInterval` | No rAF overhead for non-visual polling |
| `stream.getTracks().stop()` | Camera hardware released immediately on stop/unmount |
| `contextIsolation: true` | Renderer isolated from Node — no IPC surface exposure |
