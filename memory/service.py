import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.db import connect_db
from core.logger import setup_logger

logger = setup_logger("MemoryService")
from core.paths import WORKSPACE_ROOT


class MemoryService:
    def __init__(self, db_path: str = "storage/db/jarvis_memory.db"):
        self.db_file = (WORKSPACE_ROOT / db_path).resolve()
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_memory (
                    task_id TEXT PRIMARY KEY,
                    goal TEXT,
                    status TEXT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS solution_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_signature TEXT UNIQUE,
                    tool_name TEXT,
                    solution_fix TEXT,
                    success_count INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

        if self.get_fact("user_name") is None:
            self.set_fact("user_name", "Patron")
        if self.get_fact("user_role") is None:
            self.set_fact("user_role", "Sistem Yöneticisi / Yazılım Mimarı")
        if self.get_fact("user_os") is None:
            self.set_fact("user_os", "Windows 11")
        if self.get_fact("preferred_language") is None:
            self.set_fact("preferred_language", "Türkçe")

    def set_fact(self, key: str, value: str):
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_facts (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_fact(self, key: str) -> Optional[str]:
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_facts WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def delete_fact(self, key: str) -> bool:
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_facts WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_user_facts(self) -> Dict[str, str]:
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_facts")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def save_solution(self, error_signature: str, tool_name: str, solution_fix: str):
        clean_sig = str(error_signature).strip().lower()[:300]
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO solution_cache (error_signature, tool_name, solution_fix, success_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(error_signature) DO UPDATE SET
                    solution_fix = excluded.solution_fix,
                    success_count = success_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (clean_sig, tool_name, solution_fix))
            conn.commit()
            logger.info(f"Solution cached for error: '{clean_sig[:50]}...'")

    def find_solution(self, error_signature: str) -> Optional[Dict[str, Any]]:
        clean_sig = str(error_signature).strip().lower()[:300]
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            # Tam eslesme her zaman gecerli. Kapsama (LIKE) eslesmesi yalnizca yeterince uzun
            # (>=25 karakter) imzalar icin: kisa imzalar ilgisiz hatalara uyup yanlis recete uygulatirdi.
            cursor.execute("""
                SELECT tool_name, solution_fix, success_count
                FROM solution_cache
                WHERE error_signature = ?
                   OR (LENGTH(error_signature) >= 25 AND ? LIKE '%' || error_signature || '%')
                ORDER BY (error_signature = ?) DESC, success_count DESC LIMIT 1
            """, (clean_sig, clean_sig, clean_sig))
            row = cursor.fetchone()
            if row:
                return {
                    "tool_name": row[0],
                    "solution_fix": row[1],
                    "success_count": row[2]
                }
            return None
