"""Socket.IO klient pro komunikaci s Illustratorem pres proxy.

Vzor: C:\\Users\\stock\\Tools\\adb-mcp\\mcp\\socket_client.py
Komunikacni retezec: Python → Socket.IO → Node.js Proxy (port 3001) → CEP Plugin → Illustrator
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import threading
import logging
from queue import Queue

import socketio

from config import PROXY_URL, PROXY_TIMEOUT

logger = logging.getLogger(__name__)

APPLICATION = "illustrator"


def send_command(command: dict, timeout: int | None = None) -> dict | None:
    """Posle prikaz do Illustratoru pres proxy a ceka na odpoved.

    Args:
        command: Dict s klici 'action' a 'options'.
        timeout: Max cas cekani v sekundach.

    Returns:
        Response dict nebo None pri chybe.

    Raises:
        RuntimeError: Pri connection/timeout chybe.
        AppError: Pri chybe z Illustratoru.
    """
    wait_timeout = timeout or PROXY_TIMEOUT

    sio = socketio.Client(logger=False)
    response_queue: Queue = Queue()
    connection_failed = [False]

    @sio.event
    def connect():
        logger.info("Connected to proxy, sending command: %s", command.get("action"))
        sio.emit("command_packet", {
            "type": "command",
            "application": APPLICATION,
            "command": command,
        })

    @sio.event
    def packet_response(data):
        logger.info("Response received")
        response_queue.put(data)
        sio.disconnect()

    @sio.event
    def disconnect():
        if response_queue.empty():
            response_queue.put(None)

    @sio.event
    def connect_error(error):
        logger.error("Connection error: %s", error)
        connection_failed[0] = True
        response_queue.put(None)

    def connect_and_wait():
        try:
            sio.connect(PROXY_URL, transports=["websocket"])
            sio.wait()
        except Exception as e:
            logger.error("Socket error: %s", e)
            connection_failed[0] = True
            if response_queue.empty():
                response_queue.put(None)
            if sio.connected:
                sio.disconnect()

    client_thread = threading.Thread(target=connect_and_wait, daemon=True)
    client_thread.start()

    try:
        response = response_queue.get(timeout=wait_timeout)

        if connection_failed[0]:
            raise RuntimeError(
                f"Cannot connect to Illustrator proxy at {PROXY_URL}. "
                "Is the proxy running and Illustrator open with CEP plugin?"
            )

        if response and response.get("status") == "FAILURE":
            raise AppError(f"Illustrator error: {response.get('message', 'Unknown')}")

        return response

    except AppError:
        raise
    except Exception as e:
        if sio.connected:
            sio.disconnect()
        raise RuntimeError(
            f"Illustrator connection timed out ({wait_timeout}s). "
            f"Check proxy + CEP plugin. Error: {e}"
        )
    finally:
        if sio.connected:
            sio.disconnect()
        client_thread.join(timeout=1)


class AppError(Exception):
    """Chyba vracena z Illustratoru."""
    pass


def execute_script(script: str, timeout: int | None = None) -> dict:
    """Spusti ExtendScript v Illustratoru."""
    command = {
        "action": "executeExtendScript",
        "options": {"scriptString": script},
    }
    response = send_command(command, timeout=timeout)
    if response and "response" in response:
        return response["response"]
    return response or {}


def get_documents(timeout: int | None = None) -> dict:
    """Ziska seznam otevrenych dokumentu."""
    command = {"action": "getDocuments", "options": {}}
    return send_command(command, timeout=timeout) or {}


def get_active_document_info(timeout: int | None = None) -> dict:
    """Ziska info o aktivnim dokumentu."""
    command = {"action": "getActiveDocumentInfo", "options": {}}
    return send_command(command, timeout=timeout) or {}


async def check_connection() -> dict:
    """Zkontroluje pripojeni k proxy a Illustratoru (non-blocking wrapper)."""
    import asyncio
    try:
        result = await asyncio.get_running_loop().run_in_executor(None, lambda: get_documents(timeout=5))
        return {"connected": True, "documents": result}
    except Exception as e:
        return {"connected": False, "error": str(e)}
