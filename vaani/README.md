# VAANI — Speech & ISL Translation Desktop App

A frameless Electron desktop application for real-time Speech and Indian Sign Language (ISL) translation, integrated with a WebSocket backend.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 18 or higher | https://nodejs.org |
| npm | comes with Node | — |
| Python | 3.10 or higher | https://python.org |

Check you have them:
```bash
node -v && npm -v && python --version
```

---

## Python Backend Setup

### 1. Install Python dependencies

```bash
pip install websockets SpeechRecognition pyaudio
```

On Linux, you may also need:
```bash
sudo apt install portaudio19-dev python3-pyaudio
```

### 2. Point the server at your STT script

Open `vaani_server.py` and set `STT_COMMAND` to your script:

```python
# Line 40 in vaani_server.py
STT_COMMAND = ["python", "-u", "stt.py"]        # default (included example)
STT_COMMAND = ["python", "-u", "your_stt.py"]   # your existing script
```

### 3. Make sure your STT script prints one transcript per line

The server reads your script's **stdout** line by line. The only requirement is:

```python
# In your STT script — print each transcript on its own line, flushed
print("Hello world", flush=True)
```

Anything printed to `stderr` is ignored (use it freely for debug logs).

### 4. Run the Python server

```bash
python vaani_server.py
```

You should see:
```
12:00:00 [INFO] VAANI WebSocket server starting on ws://localhost:8000/ws
12:00:00 [INFO] Server ready — waiting for VAANI to connect…
```

### 5. Start the Electron app (in a separate terminal)

```bash
npm start
```

Then in the app, click **CONNECT** — the title bar dot turns cyan.
Click **▶ Start Translation** and speak into your microphone.

---

## Project Structure

```
vaani/
├── assets/
│   └── icon.png          ← App icon
├── src/
│   ├── main.js           ← Electron main process (creates window)
│   ├── preload.js        ← Secure IPC bridge (main ↔ renderer)
│   ├── index.html        ← App UI
│   └── renderer.js       ← UI logic + WebSocket client
├── package.json
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
cd vaani
npm install
```

This downloads Electron (~100 MB on first run).

### 2. Run the app

```bash
npm start
```

The VAANI window will open. It is a frameless window with custom title bar controls (minimize / maximize / close).

---

## Connecting to your backend

1. Start your WebSocket backend server (e.g. `ws://localhost:8000/ws`)
2. In the VAANI config bar at the top, enter your endpoint
3. Click **CONNECT** — the dot in the title bar turns cyan when connected

---

## WebSocket Message Protocol

### Frontend → Backend (sent as JSON)

| Event | Payload |
|-------|---------|
| Start speech (mic) | `{ "type": "start_speech", "source": "mic" }` |
| Start speech (URL) | `{ "type": "start_speech", "source": "url", "url": "https://..." }` |
| Stop speech | `{ "type": "stop_speech" }` |
| Start ISL | `{ "type": "start_isl" }` |
| Stop ISL | `{ "type": "stop_isl" }` |

### Backend → Frontend (expected JSON)

| `type` field | Required fields | Effect |
|---|---|---|
| `speech_transcript` | `text: string` | Appends text to transcription box |
| `transcript` | `text: string` | Same as above (alias) |
| `isl_signs` | `word: string`, `description: string` | Adds ISL entry row |
| `isl` | `word: string`, `description: string` | Same as above (alias) |
| `speech_status` | `status: "running"\|"idle"\|"error"` | Updates speech status dot |
| `isl_status` | `status: "running"\|"idle"\|"error"` | Updates ISL status dot |
| `error` | `message: string` | Logged to DevTools console |

---

## Testing without a backend

Open DevTools (`Ctrl+Shift+I` or `Cmd+Shift+I`) and run:

```js
// Simulate a speech transcript chunk
simulate('transcript', 'Hello, how are you?')

// Simulate an ISL sign description
simulate('isl', 'HELLO', 'Right hand raised to forehead level, palm facing outward, moves forward and downward.')
```

---

## Building a distributable

Build for your current platform:

```bash
# Windows (.exe installer)
npm run build:win

# macOS (.dmg)
npm run build:mac

# Linux (.AppImage)
npm run build:linux
```

Output goes to the `dist/` folder.

> **Note:** Building for macOS requires running on a Mac. Cross-platform builds require extra tooling (see `electron-builder` docs).

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl/Cmd + R` | Reload window |
| `Ctrl/Cmd + Shift + I` | Toggle DevTools |
| `Ctrl/Cmd + Q` | Quit |
| `F11` | Toggle fullscreen |

---

## Troubleshooting

**App won't open / white screen**
- Run `npm start` from the terminal and check for errors
- Make sure Node 18+ is installed

**WebSocket won't connect**
- Ensure your backend is running before connecting
- Check the URL scheme: use `ws://` for local, `wss://` for TLS

**Fonts not loading (offline)**
- The app loads IBM Plex Mono from Google Fonts on first run
- For fully offline use, download the fonts and reference them locally in `src/index.html`
