# server.py
# asyncio + websockets server that streams predictions to the frontend.
#
# Every camera frame produces a JSON payload broadcast to all connected clients:
#
#   {
#     "character":          "A",      // predicted label, or null
#     "confidence":         0.94,     // 0-1 float, or null
#     "accepted":           true,     // confidence >= threshold
#     "sentence":           "BALL",   // accumulated text
#     "stability_progress": 0.6,      // 0-1 progress toward committing
#     "landmarks": [                  // 21 points of the first hand
#       {"x": 0.42, "y": 0.31}, ...
#     ]
#   }
#
# Clients can send:
#   "CLEAR"     → empty the sentence
#   "BACKSPACE" → remove the last character
#
# Usage:
#   python server.py
#   python server.py --host 127.0.0.1 --port 9000

import argparse
import asyncio
import json
import logging
import queue
import threading
from typing import Any, Dict, Optional, Set

import cv2
import websockets
from websockets.server import WebSocketServerProtocol

from classifier import SignClassifier
from config import CAMERA_INDEX, WS_HOST, WS_PORT
from hand_tracker import HandTracker
from sentence_builder import SentenceBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("server")

# ── Shared state ──────────────────────────────────────────────────────────────
_frame_queue: queue.Queue = queue.Queue(maxsize=2)
_clients: Set[WebSocketServerProtocol] = set()
_clients_lock = asyncio.Lock()
_sentence_builder = SentenceBuilder()


# ── Inference thread (runs OpenCV + MediaPipe outside asyncio) ────────────────
def _inference_worker(camera: int) -> None:
    log.info("Opening camera (index %d) ...", camera)
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        log.error("Cannot open camera index %d", camera)
        _frame_queue.put(None)
        return

    try:
        classifier = SignClassifier()
    except FileNotFoundError as exc:
        log.error("%s", exc)
        cap.release()
        _frame_queue.put(None)
        return

    tracker = HandTracker()
    log.info("Inference worker ready.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                log.warning("Failed to read frame from camera.")
                continue

            tracking = tracker.process(frame)

            payload: Dict[str, Any] = {
                "character":          None,
                "confidence":         None,
                "accepted":           False,
                "sentence":           _sentence_builder.sentence,
                "stability_progress": _sentence_builder.stability_progress,
                "landmarks":          [],
            }

            if tracking.hand_detected and tracking.features is not None:
                pred = classifier.predict(tracking.features)
                if pred is not None:
                    payload["character"]  = pred.character
                    payload["confidence"] = pred.confidence
                    payload["accepted"]   = pred.accepted

                    _sentence_builder.update(
                        pred.character if pred.accepted else None
                    )
                    payload["sentence"]            = _sentence_builder.sentence
                    payload["stability_progress"]  = _sentence_builder.stability_progress

                if tracking.landmarks:
                    payload["landmarks"] = [
                        {"x": round(x, 5), "y": round(y, 5)}
                        for x, y in tracking.landmarks[0]
                    ]

            try:
                _frame_queue.put_nowait(payload)
            except queue.Full:
                pass   # drop frame — keep latency low

    finally:
        tracker.close()
        cap.release()
        log.info("Camera released.")


# ── Broadcast loop ────────────────────────────────────────────────────────────
async def _broadcast_loop() -> None:
    loop = asyncio.get_running_loop()
    while True:
        payload = await loop.run_in_executor(None, _frame_queue.get)
        if payload is None:
            log.error("Inference worker signalled failure — stopping.")
            break

        message = json.dumps(payload)
        async with _clients_lock:
            dead: Set = set()
            for ws in _clients:
                try:
                    await ws.send(message)
                except websockets.ConnectionClosed:
                    dead.add(ws)
            _clients -= dead


# ── Per-client handler ────────────────────────────────────────────────────────
async def _handle_client(ws: WebSocketServerProtocol) -> None:
    async with _clients_lock:
        _clients.add(ws)
    addr = ws.remote_address
    log.info("Client connected: %s", addr)

    try:
        async for message in ws:
            cmd = message.strip().upper()
            if cmd == "CLEAR":
                _sentence_builder.clear()
                log.info("Sentence cleared by %s", addr)
            elif cmd == "BACKSPACE":
                _sentence_builder.update("BACKSPACE")
                log.info("Backspace from %s", addr)
    except websockets.ConnectionClosed:
        pass
    finally:
        async with _clients_lock:
            _clients.discard(ws)
        log.info("Client disconnected: %s", addr)


# ── Entry point ───────────────────────────────────────────────────────────────
def run(host: str = WS_HOST, port: int = WS_PORT, camera: int = CAMERA_INDEX) -> None:
    thread = threading.Thread(
        target=_inference_worker, args=(camera,), daemon=True, name="inference"
    )
    thread.start()

    async def _main():
        broadcast = asyncio.create_task(_broadcast_loop())
        log.info("WebSocket server listening on ws://%s:%d", host, port)
        async with websockets.serve(_handle_client, host, port):
            await broadcast

    asyncio.run(_main())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the sign-language WebSocket server.")
    parser.add_argument("--host",   default=WS_HOST,    help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port",   type=int, default=WS_PORT,   help="Bind port (default: 8765)")
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX, help="Camera index (default: 0)")
    args = parser.parse_args()
    run(host=args.host, port=args.port, camera=args.camera)


if __name__ == "__main__":
    main()
