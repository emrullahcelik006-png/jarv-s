import sys
import os
import asyncio
from pathlib import Path

# Fix Python Module Search Path to include Project Root
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from core.logger import setup_logger
from services.background_agent import background_agent
from tools.system import NetworkPortHealthTool
from tools.notification import NotificationTool

logger = setup_logger("SystemTray")


def create_tray_icon():
    """Generates a native 64x64 JARVIS Orb icon in memory."""
    image = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=(0, 212, 255, 255), outline=(0, 100, 200, 255))
    draw.ellipse((20, 20, 44, 44), fill=(10, 25, 50, 255))
    draw.ellipse((26, 26, 38, 38), fill=(0, 255, 200, 255))
    return image


def on_check_ports(icon, item_obj):
    tool = NetworkPortHealthTool()
    res = asyncio.run(tool.execute())
    notify = NotificationTool()
    asyncio.run(notify.execute(title="JARVIS Port Sensörü", message=f"Aktif Servisler: {res.metadata.get('active_services', 0)}/6"))


def on_send_toast(icon, item_obj):
    notify = NotificationTool()
    asyncio.run(notify.execute(title="JARVIS Masaüstü Operatörü", message="Sistemler çevrimiçi ve arka planda hazır patron."))


def on_exit(icon, item_obj):
    logger.info("System tray servisi kapatılıyor...")
    icon.stop()


def run_tray():
    image = create_tray_icon()
    menu = (
        item("🤖 JARVIS Status: ONLINE", lambda: None, enabled=False),
        item("🌐 Ağ & Port Sağlığı Tara", on_check_ports),
        item("🔔 Test Bildirimi Gönder", on_send_toast),
        item("❌ Çıkış", on_exit),
    )
    icon = pystray.Icon("JARVIS_Agent", image, "JARVIS AI Agent Operating Layer", menu)
    logger.info("JARVIS Windows System Tray (Görev Çubuğu) servisi başlatıldı.")
    icon.run()


if __name__ == "__main__":
    run_tray()
