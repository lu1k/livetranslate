"""
vaani_server.py — WebSocket bridge for VAANI
=============================================
Manages two independent subprocesses:
  • STT  — speech-to-text  (started by "start_speech" from Electron)
  • ISL  — sign-language   (started by "start_isl"    from Electron)

Both scripts communicate via stdout: print one result per line, flushed.

STT  stdout format:  plain text transcript
    "Hello how are you"

ISL  stdout format:  WORD|Description   (pipe-separated)
    "HELLO|Right hand raised to forehead, palm outward, sweeps forward."
    "WATER|Both hands form a W shape and tap the chin twice."

If your ISL script only prints plain text (no pipe), the whole line
is shown in the description column with no word label — also fine.

Usage:
    python vaani_server.py

Then in VAANI set endpoint to:  ws://localhost:8000/ws

Requirements:
    pip install websockets
"""

import asyncio
import json
import logging
import subprocess

import websockets
from websockets.server import WebSocketServerProtocol

# ── Configuration ──────────────────────────────────────────────────────────────

HOST = "localhost"
PORT = 8000

# ❶ Point at your STT script
STT_COMMAND = ["python", "-u", r"C:\project\livetranslate04\livetranslate\main.py"]

# ❷ Point at your ISL script
ISL_COMMAND = ["python", "-u", r"C:\project\livetranslate04\livetranslate\sign_module\isl_stdout.py"]

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vaani")

# ── Generic subprocess wrapper ─────────────────────────────────────────────────

class ManagedProcess:
    """
    Spawns a subprocess, reads its stdout line-by-line in a background
    asyncio task, and calls on_line(line) for each non-empty line.
    """

    def __init__(self, name: str, command: list, on_line):
        self.name      = name
        self.command   = command
        self.on_line   = on_line          # async callback(line: str)
        self._proc     = None
        self._task     = None

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        if self._proc and self._proc.poll() is None:
            log.warning("[%s] already running — ignoring start", self.name)
            return
        log.info("[%s] spawning: %s", self.name, " ".join(self.command))
        self._proc = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,                    # line-buffered
        )
        self._task = asyncio.create_task(self._read_loop())

    def stop(self):
        self._cancel_task()
        if self._proc and self._proc.poll() is None:
            log.info("[%s] terminating (pid=%d)", self.name, self._proc.pid)
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    async def stop_async(self):
        """Cancel reader task and wait for it before stopping process."""
        self._cancel_task()
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.stop()

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ── internal ───────────────────────────────────────────────────────────────

    def _cancel_task(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _read_loop(self):
        loop = asyncio.get_event_loop()
        while self._proc and self._proc.poll() is None:
            try:
                line = await loop.run_in_executor(None, self._proc.stdout.readline)
            except Exception as exc:
                log.error("[%s] stdout read error: %s", self.name, exc)
                break
            if not line:
                break                     # EOF — process ended
            text = line.rstrip("\n").strip()
            if text:
                await self.on_line(text)

        if self._proc:
            log.info("[%s] process exited (rc=%s)", self.name, self._proc.poll())
            self._proc = None

# ── Session ────────────────────────────────────────────────────────────────────

class Session:
    def __init__(self, ws: WebSocketServerProtocol):
        self.ws  = ws
        self.stt = ManagedProcess("STT", STT_COMMAND, self._on_stt_line)
        self.isl = ManagedProcess("ISL", ISL_COMMAND, self._on_isl_line)

    # ── send helpers ───────────────────────────────────────────────────────────

    async def send(self, obj: dict):
        try:
            await self.ws.send(json.dumps(obj))
        except websockets.ConnectionClosed:
            pass

    async def send_status(self, module: str, status: str):
        await self.send({"type": f"{module}_status", "status": status})

    # ── STT stdout callback ────────────────────────────────────────────────────

    async def _on_stt_line(self, line: str):
        """
        Called for every line your STT script prints.
        Forwards it to Electron as a speech_transcript message.
        """
        log.info("[STT] → %r", line)
        await self.send({"type": "speech_transcript", "text": line})
        if not self.stt.running:
            await self.send_status("speech", "idle")

    # ── ISL stdout callback ────────────────────────────────────────────────────

    async def _on_isl_line(self, line: str):
        """
        Called for every line your ISL script prints.

        Expected format — pipe-separated:
            WORD|Description of the ISL gesture

        Examples:
            HELLO|Right hand raised to forehead, palm outward, sweeps forward.
            WATER|Both hands form a W shape and tap the chin twice.
            PLEASE|Right hand flat against chest, moves in a circular motion.

        If your script prints plain text with no pipe separator, the full
        line becomes the description and the word label is left empty.
        """
        log.info("[ISL] → %r", line)

        if "|" in line:
            word, _, description = line.partition("|")
            word        = word.strip()
            description = description.strip()
        else:
            # Plain text fallback — no word label
            word        = ""
            description = line.strip()

        await self.send({
            "type":        "isl_signs",
            "word":        word,
            "description": description,
        })

        if not self.isl.running:
            await self.send_status("isl", "idle")

    # ── command handlers ───────────────────────────────────────────────────────

    async def handle_start_speech(self):
        self.stt.start()
        await self.send_status("speech", "running")

    async def handle_stop_speech(self):
        await self.stt.stop_async()
        await self.send_status("speech", "idle")

    async def handle_start_isl(self):
        self.isl.start()
        await self.send_status("isl", "running")

    async def handle_stop_isl(self):
        await self.isl.stop_async()
        await self.send_status("isl", "idle")

    # ── cleanup ────────────────────────────────────────────────────────────────

    async def cleanup(self):
        await self.stt.stop_async()
        await self.isl.stop_async()

# ── WebSocket handler ──────────────────────────────────────────────────────────

async def handle(ws: WebSocketServerProtocol):
    remote = ws.remote_address
    log.info("Client connected: %s:%s", remote[0], remote[1])
    session = Session(ws)

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Non-JSON message: %r", raw)
                continue

            t = msg.get("type", "")
            log.info("← %s", t)

            if   t == "start_speech": await session.handle_start_speech()
            elif t == "stop_speech":  await session.handle_stop_speech()
            elif t == "start_isl":    await session.handle_start_isl()
            elif t == "stop_isl":     await session.handle_stop_isl()
            else: log.warning("Unknown message type: %r", t)

    except websockets.ConnectionClosedOK:
        log.info("Client disconnected cleanly")
    except websockets.ConnectionClosedError as exc:
        log.warning("Client disconnected with error: %s", exc)
    finally:
        await session.cleanup()
        log.info("Session cleaned up")

# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    log.info("VAANI server  ws://%s:%d", HOST, PORT)
    log.info("STT: %s", " ".join(STT_COMMAND))
    log.info("ISL: %s", " ".join(ISL_COMMAND))

    async with websockets.serve(handle, HOST, PORT):
        log.info("Ready — waiting for VAANI to connect…")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Server stopped.")
