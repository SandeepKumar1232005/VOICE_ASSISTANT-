"""
Nexus AI — API Server

FastAPI server for the floating companion UI.
Provides REST and WebSocket endpoints to interact with the Nexus AI core.
"""

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nexus_ai.utils.logger import get_logger

logger = get_logger("APIServer")

app = FastAPI(title="Nexus AI", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")

manager = ConnectionManager()


class CommandRequest(BaseModel):
    command: str


# Reference to the main assistant instance
nexus_assistant = None

def init_app(assistant_instance):
    """Link the running NexusAssistant instance to the API."""
    global nexus_assistant
    nexus_assistant = assistant_instance


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"WS received: {data}")
            # If the UI sends a text command directly
            if nexus_assistant and data:
                asyncio.create_task(nexus_assistant.process_command(data))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/command")
async def execute_command(req: CommandRequest):
    """Execute a text command directly from the UI."""
    if not nexus_assistant:
        return {"success": False, "message": "Nexus Assistant not initialized."}
        
    logger.info(f"API received command: {req.command}")
    
    # Broadcast to UI that we are processing
    await manager.broadcast({"event": "status", "status": "processing", "command": req.command})
    
    # Process asynchronously
    asyncio.create_task(nexus_assistant.process_command(req.command))
    
    return {"success": True, "message": "Command queued"}


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return {
        "status": "online",
        "assistant_name": nexus_assistant.assistant_name if nexus_assistant else "Nexus"
    }


import os
ui_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")


def run_server(assistant_instance, host="127.0.0.1", port=8000):
    """Run the Uvicorn server in a separate thread/loop."""
    import uvicorn
    import threading
    
    init_app(assistant_instance)
    
    def _run():
        logger.info(f"Starting Nexus UI Server on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")
        
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
