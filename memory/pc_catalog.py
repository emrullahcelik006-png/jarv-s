import os
import re
import sqlite3
import subprocess
import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional
from core.db import connect_db
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT

logger = setup_logger("PCCatalog")
USER_HOME = Path(os.path.expanduser("~")).resolve()

# Kaldirma/yardim/okubeni gibi kisayollar katalogu kirletir ve "ac" komutunu yanlis hedefe goturur.
JUNK_NAME_RE = re.compile(
    r"uninstall|kald[ıi]r|readme|\bhelp\b|license|lisans|web sitesi|website|release notes|documentation|\bsetup\b|install(er)?\b",
    re.IGNORECASE,
)

EXCLUDE_DIRS = {".venv", "venv", "site-packages", "node_modules", "appdata", "__pycache__", ".git", ".pytest_cache"}


class PCCatalogService:
    def __init__(self, db_path: str = "storage/db/pc_catalog.db"):
        _p = Path(db_path)
        self.db_file = _p if _p.is_absolute() else (WORKSPACE_ROOT / _p)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pc_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    item_type TEXT,
                    path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def scan_and_index_pc(self) -> int:
        """Fully dynamic scan of Windows Shell AppsFolder, Start Menu, Desktop & User paths."""
        items_to_insert = []

        # 1. Native Windows Apps via Shell Get-StartApps API
        try:
            ps_cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45
            )
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    data = [data]
                for app in data:
                    raw_name = str(app.get("Name", "")).strip()
                    app_id = str(app.get("AppID", "")).strip()
                    if raw_name and app_id:
                        clean_name = re.sub(r"[^\w\s-]", "", raw_name).lower().strip()
                        if clean_name and not JUNK_NAME_RE.search(clean_name):
                            items_to_insert.append((clean_name, "app", app_id))
        except Exception as e:
            logger.error(f"StartApps scan error: {e}")

        # 2. Desktop & Start Menu Shortcut Paths
        search_paths = [
            USER_HOME / "Desktop",
            USER_HOME / "OneDrive" / "Desktop",
            Path(r"C:\Users\Public\Desktop"),
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
            USER_HOME / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs",
            USER_HOME / r"AppData\Roaming\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar",
        ]

        for base_dir in search_paths:
            if not base_dir.exists():
                continue

            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d.lower() not in EXCLUDE_DIRS and not d.startswith(".")]

                for file in files:
                    ext = Path(file).suffix.lower()
                    if ext in (".exe", ".lnk", ".url"):
                        raw_stem = Path(file).stem
                        clean_name = re.sub(r"[^\w\s-]", "", raw_stem).lower().strip()
                        full_path = str(Path(root) / file)
                        if clean_name and not JUNK_NAME_RE.search(clean_name):
                            items_to_insert.append((clean_name, "app", full_path))

        # 3. Write to SQLite
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            # Tarama bos/basarisiz dondugunde mevcut katalog silinmesin.
            if not items_to_insert:
                logger.warning("PC Catalog taramasi bos dondu; mevcut katalog korundu.")
                return 0
            cursor.execute("DELETE FROM pc_items")
            for name, itype, path in items_to_insert:
                try:
                    # OR IGNORE: ayni adli ilk kayit (Shell AppID) korunur; sonraki kisayol onu ezmez.
                    cursor.execute(
                        "INSERT OR IGNORE INTO pc_items (name, item_type, path) VALUES (?, ?, ?)",
                        (name, itype, path)
                    )
                except Exception:
                    pass
            conn.commit()

        logger.info(f"PC Catalog Scan Completed: {len(items_to_insert)} items stored.")
        return len(items_to_insert)

    def search_item(self, query: str) -> Optional[Dict[str, str]]:
        """100% Generic Search Engine. Pure ASCII matching & SequenceMatcher."""
        clean_q = re.sub(r"[^\w\s.-]", "", query).lower().strip()
        clean_q = re.sub(r"\b(open|launch|run|start|open\s+app|launch\r+app)\b", "", clean_q).strip()

        if not clean_q or len(clean_q) < 2:
            return None

        # Direct Web Domain Check
        if clean_q.startswith(("http://", "https://")) or any(clean_q.endswith(ext) for ext in (".com", ".org", ".net", ".io")):
            url = clean_q if clean_q.startswith(("http://", "https://")) else f"https://{clean_q}"
            return {"name": clean_q, "item_type": "url", "path": url}

        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()

            # TIER 1: Exact Name Match
            cursor.execute("SELECT name, item_type, path FROM pc_items WHERE name = ? LIMIT 1", (clean_q,))
            row = cursor.fetchone()
            if row:
                return {"name": row[0], "item_type": row[1], "path": row[2]}

            # TIER 2: Prefix Match
            cursor.execute("SELECT name, item_type, path FROM pc_items WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1", (f"{clean_q}%",))
            row = cursor.fetchone()
            if row:
                return {"name": row[0], "item_type": row[1], "path": row[2]}

            # TIER 3: Substring Match
            cursor.execute("SELECT name, item_type, path FROM pc_items WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1", (f"%{clean_q}%",))
            row = cursor.fetchone()
            if row:
                return {"name": row[0], "item_type": row[1], "path": row[2]}

            # TIER 4: Dynamic Sequence Matcher
            cursor.execute("SELECT name, item_type, path FROM pc_items WHERE item_type = 'app'")
            all_apps = cursor.fetchall()

            best_match = None
            highest_score = 0.0

            for db_name, item_type, path in all_apps:
                score = SequenceMatcher(None, clean_q, db_name).ratio()
                if score > highest_score:
                    highest_score = score
                    best_match = {"name": db_name, "item_type": item_type, "path": path}

            if best_match and highest_score >= 0.70:
                logger.info(f"Catalog Match: '{query}' -> '{best_match['name']}' ({highest_score:.2f})")
                return best_match

        return None
