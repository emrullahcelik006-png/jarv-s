import sys
import os
import socket
import threading
import time
from pathlib import Path

# Fix Python Module Search Path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import uvicorn
import webview
from core.logger import setup_logger
from core.config import get_settings

logger = setup_logger("DesktopHUD")
settings = get_settings()


def run_uvicorn_server():
    """Runs FastAPI Backend silently in a background thread."""
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="error",
        access_log=False
    )


def _wait_for_server(host: str = "127.0.0.1", port: int = 8000, max_wait: float = 15.0) -> bool:
    """Polls local TCP socket until FastAPI server is bound and listening."""
    start_t = time.time()
    while time.time() - start_t < max_wait:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False


def launch_native_desktop_hud():
    """Launches JARVIS as a Native Windows Desktop App with zero race condition."""
    if not _wait_for_server(max_wait=0.5):
        logger.info("Starting background FastAPI API server...")
        server_thread = threading.Thread(target=run_uvicorn_server, daemon=True)
        server_thread.start()

        logger.info("Waiting for FastAPI server initialization & catalog indexing...")
        if not _wait_for_server(max_wait=15.0):
            logger.error("FastAPI server failed to bind within 15 seconds.")
            return

    logger.info("Server is ONLINE! Launching Native Windows Desktop HUD Window...")

    # Cache-busting URL parameter forces WebView2 to load fresh CSS/JS
    hud_url = f"http://127.0.0.1:8000/?v={int(time.time())}"

    window = webview.create_window(
        title="J.A.R.V.I.S. Mission Control",
        url=hud_url,
        width=1280,
        height=800,
        resizable=True,
        frameless=False,
        easy_drag=True,
        on_top=False,
        background_color="#060913"
    )

    webview.start(private_mode=False)


if __name__ == "__main__":
    launch_native_desktop_hud()

