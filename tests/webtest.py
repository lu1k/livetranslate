import sys
sys.path.insert(1, '/websocket_server/')
from websocket_server import app
import threading
import uvicorn

isRunning = True
def start_websocket():
    uvicorn.run(app, host="127.0.0.1", port=8000)

threading.Thread(target=start_websocket, daemon=True).start()
while isRunning:
    pass