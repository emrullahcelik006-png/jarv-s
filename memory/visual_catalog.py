import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from core.db import connect_db
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT

logger = setup_logger("VisualCatalog")


class VisualAppCatalog:
    """Uygulamalarin gorsel simgelerini ve ekran koordinat referanslarini saklayan veritabani."""

    def __init__(self, db_path: str = "storage/db/jarvis_visual_catalog.db"):
        _p = Path(db_path)
        self.db_file = _p if _p.is_absolute() else (WORKSPACE_ROOT / _p)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir = (WORKSPACE_ROOT / "storage" / "app_visuals")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS visual_apps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT UNIQUE,
                    icon_image_path TEXT,
                    description TEXT,
                    mapped_action TEXT
                )
            """)
            conn.commit()

        # Varsayilan Gorsel Eslestirmeler
        self.register_visual_app("outlook", "Outlook E-Posta İstemcisi", "app_launcher")
        self.register_visual_app("steam", "Steam Oyun Platformu", "app_launcher")
        self.register_visual_app("chrome", "Google Chrome Tarayıcısı", "app_launcher")

    def register_visual_app(self, app_name: str, description: str, mapped_action: str = "app_launcher") -> bool:
        icon_path = str(self.images_dir / f"{app_name.lower()}.png")
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO visual_apps (app_name, icon_image_path, description, mapped_action) VALUES (?, ?, ?, ?)",
                (app_name.lower(), icon_path, description, mapped_action)
            )
            conn.commit()
            return True

    def get_registered_apps(self) -> List[Dict[str, str]]:
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT app_name, icon_image_path, description, mapped_action FROM visual_apps")
            return [
                {"app_name": r[0], "icon_path": r[1], "description": r[2], "action": r[3]}
                for r in cursor.fetchall()
            ]
