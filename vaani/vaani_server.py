"""
vaani_server.py — WebSocket bridge for VAANI
=============================================
Wraps your existing STT script (which prints transcripts to stdout)
inside a WebSocket server that VAANI's Electron frontend connects to.

Usage:
    python vaani_server.py

Then in the VAANI app set the endpoint to:  ws://localhost:8000/ws

How it works:
    1. Electron connects and sends  { "type": "start_speech" }
    2. This server spawns your STT script as a subprocess
    3. Every line your STT script prints to stdout is forwarded to
       Electron as  { "type": "speech_transcript", "text": "..." }
    4. When Electron sends { "type": "stop_speech" } the subprocess
       is terminated cleanly

Requirements:
    pip install websockets
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path

import websockets
from websockets.server import WebSocketServerProtocol

# ── Configuration ──────────────────────────────────────────────────────────────

HOST = "localhost"
PORT = 8000

# ❶  Point this at your STT script / command.
#    Examples:
#      STT_COMMAND = ["python", "stt.py"]
#      STT_COMMAND = ["python", "/absolute/path/to/stt.py"]
#      STT_COMMAND = ["python", "-u", "stt.py"]   # -u = unbuffered (recommended)
STT_COMMAND = ["python", "-u", "stt.py"]

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vaani")

# ── Per-connection state ───────────────────────────────────────────────────────

class Session:
    def __init__(self, ws: WebSocketServerProtocol):
        self.ws = ws
        self.stt_proc: subprocess.Popen | None = None
        self.reader_task: asyncio.Task | None = None

    # ── helpers ────────────────────────────────────────────────────────────────

    async def send(self, obj: dict):
        try:
            await self.ws.send(json.dumps(obj))
        except websockets.ConnectionClosed:
            pass

    async def send_status(self, module: str, status: str):
        await self.send({"type": f"{module}_status", "status": status})

    # ── STT subprocess ─────────────────────────────────────────────────────────

    def start_stt(self):
        """Spawn the STT subprocess."""
        if self.stt_proc and self.stt_proc.poll() is None:
            log.warning("STT already running — ignoring start request")
            return

        log.info("Spawning STT: %s", " ".join(STT_COMMAND))
        self.stt_proc = subprocess.Popen(
            STT_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,          # line-buffered
        )

    def stop_stt(self):
        """Terminate the STT subprocess if running."""
        if self.stt_proc and self.stt_proc.poll() is None:
            log.info("Terminating STT subprocess (pid=%d)", self.stt_proc.pid)
            self.stt_proc.terminate()
            try:
                self.stt_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.stt_proc.kill()
        self.stt_proc = None

    # ── Async stdout reader ────────────────────────────────────────────────────

    async def _read_stdout(self):
        """
        Read lines from the STT process stdout and forward each one
        to the Electron frontend as a speech_transcript message.

        Your STT script should print one transcript per line, e.g.:
            print("Hello world", flush=True)
        """
        loop = asyncio.get_event_loop()

        while self.stt_proc and self.stt_proc.poll() is None:
            try:
                # Read a line without blocking the event loop
                line = await loop.run_in_executor(
                    None, self.stt_proc.stdout.readline
                )
            except Exception as exc:
                log.error("stdout read error: %s", exc)
                break

            if not line:
                break                       # EOF — process ended

            text = line.rstrip("\n").strip()
            if text:
                log.info("Transcript → Electron: %r", text)
                await self.send({
                    "type": "speech_transcript",
                    "text": text,
                })

        # Process ended on its own
        if self.stt_proc:
            log.info("STT process exited (rc=%s)", self.stt_proc.returncode)
            self.stt_proc = None
            await self.send_status("speech", "idle")

    async def start_reading(self):
        """Start the background task that reads STT stdout."""
        if self.reader_task and not self.reader_task.done():
            self.reader_task.cancel()
        self.reader_task = asyncio.create_task(self._read_stdout())

    async def stop_reading(self):
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
            self.reader_task = None

    # ── Cleanup ────────────────────────────────────────────────────────────────

    async def cleanup(self):
        await self.stop_reading()
        self.stop_stt()


# ── WebSocket handler ──────────────────────────────────────────────────────────

async def handle(ws: WebSocketServerProtocol):
    remote = ws.remote_address
    log.info("Client connected: %s:%s", *remote)
    session = Session(ws)

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Non-JSON message received: %r", raw)
                continue

            msg_type = msg.get("type", "")
            log.info("← %s", msg_type)

            # ── Speech commands ──────────────────────────────────────────────

            if msg_type == "start_speech":
                session.start_stt()
                await session.start_reading()
                await session.send_status("speech", "running")

            elif msg_type == "stop_speech":
                await session.stop_reading()
                session.stop_stt()
                await session.send_status("speech", "idle")

            # ── ISL commands (hook in your ISL logic here) ───────────────────

            elif msg_type == "start_isl":
                # TODO: start your ISL translation process here
                # For now, just acknowledge
                await session.send_status("isl", "running")
                log.info("ISL start received — wire up your ISL module here")

            elif msg_type == "stop_isl":
                # TODO: stop your ISL translation process here
                await session.send_status("isl", "idle")

            else:
                log.warning("Unknown message type: %r", msg_type)

    except websockets.ConnectionClosedOK:
        log.info("Client disconnected cleanly: %s:%s", *remote)
    except websockets.ConnectionClosedError as exc:
        log.warning("Client disconnected with error: %s", exc)
    finally:
        await session.cleanup()
        log.info("Session cleaned up for %s:%s", *remote)


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    log.info("VAANI WebSocket server starting on ws://%s:%d/ws", HOST, PORT)
    log.info("STT command: %s", " ".join(STT_COMMAND))

    async with websockets.serve(handle, HOST, PORT, subprotocols=None):
        log.info("Server ready — waiting for VAANI to connect…")
        await asyncio.Future()          # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Server stopped.")
