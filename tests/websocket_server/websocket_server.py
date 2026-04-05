from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# store connected clients
clients = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)

    print("Client connected")

    try:
        while True:
            # Keep connection alive (receive dummy messages if needed)
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)
        print("Client disconnected")


# function to send data to all clients
async def broadcast(message: str):
    dead_clients = []

    for client in clients:
        try:
            await client.send_text(message)
        except:
            dead_clients.append(client)

    # cleanup disconnected clients
    for client in dead_clients:
        clients.remove(client)